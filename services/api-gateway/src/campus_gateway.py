from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

API_SRC = Path(__file__).resolve().parent
AUTH_SRC = Path(__file__).resolve().parents[2] / "auth-service" / "src"
WORKFLOW_SRC = Path(__file__).resolve().parents[2] / "workflow-service" / "src"
WECOM_SRC = Path(__file__).resolve().parents[2] / "wecom-adapter" / "src"
sys.path.extend([str(API_SRC), str(AUTH_SRC), str(WORKFLOW_SRC), str(WECOM_SRC)])

from audit_store import write_audit_event  # noqa: E402
from campus_auth import handle_wecom_callback, issue_wecom_state  # noqa: E402
from campus_domain import (  # noqa: E402
    ROLE_PARENT,
    ROLE_VENDOR,
    assign_repair_ticket,
    cancel_meal_order,
    close_repair_ticket,
    confirm_delivery,
    create_leave_request,
    create_meal_order,
    create_repair_ticket,
    decide_leave_request,
    ensure_demo_school_data,
    generate_daily_report,
    get_leave_request,
    get_meal_summary,
    get_repair_ticket,
    list_leave_requests,
    list_repair_tickets,
    complete_repair_ticket,
    run_repair_timeouts,
)
from event_schema import EventType, make_event  # noqa: E402
from wecom_adapter import WeComAdapter  # noqa: E402


CAMPUS_STATE_FIELDS = {"redirect_path"}
LEAVE_CREATE_FIELDS = {"student_id", "type", "start_time", "end_time", "reason", "attachments_json"}
LEAVE_DECISION_FIELDS = {"note"}
MEAL_CREATE_FIELDS = {"student_id", "meal_date", "meal_type", "action", "dietary_note"}
MEAL_CANCEL_FIELDS = set()
DELIVERY_CONFIRM_FIELDS = {"token", "note"}
REPAIR_CREATE_FIELDS = {"class_id", "location_type", "location_detail", "category", "priority", "description", "deadline_at", "images_json"}
REPAIR_ASSIGN_FIELDS = {"assignee_id"}
REPAIR_COMPLETE_FIELDS = {"result_note", "result_images_json"}
REPAIR_CLOSE_FIELDS = set()


def _reject_untrusted_fields(payload: dict[str, Any], allowed: set[str]) -> None:
    for key in payload:
        if key not in allowed:
            raise ValueError(f"Forbidden request field: {key}")


def _audit_identity(identity: dict[str, Any]) -> dict[str, str]:
    return {
        "user_id": str(identity.get("user_id", "")),
        "role": str(identity.get("role", "")),
        "campus": str(identity.get("campus", identity.get("school_id", ""))),
    }


def _write_campus_event(project_root: Path, event_type: str, identity: dict[str, Any], metadata: dict[str, Any]) -> None:
    ids = _audit_identity(identity)
    write_audit_event(
        project_root,
        make_event(
            event_type,
            user_id=ids["user_id"],
            role=ids["role"],
            campus=ids["campus"],
            entrypoint="campus",
            metadata=metadata,
        ),
    )


def _wecom_adapter(project_root: Path) -> WeComAdapter:
    return WeComAdapter(project_root)


def issue_campus_wecom_state(payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, CAMPUS_STATE_FIELDS)
    result = issue_wecom_state(project_root, redirect_path=str(payload.get("redirect_path", "/h5")))
    _write_campus_event(project_root, EventType.CAMPUS_AUTH_STATE_ISSUED, identity, {"redirect_path": result["redirect_path"]})
    return result


def _database_wecom_identity(wecom_userid: str) -> dict[str, Any] | None:
    mealbot_src = Path(__file__).resolve().parents[2] / "mealbot-service" / "src"
    if str(mealbot_src) not in sys.path:
        sys.path.insert(0, str(mealbot_src))
    from app.db.repositories.campus_identity import resolve_wecom_identity

    return resolve_wecom_identity(wecom_userid, os.environ.get("WECOM_SCHOOL_ID", "school_demo"))


def get_campus_wecom_start(query: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    redirect_path = str(query.get("redirect_path", "/h5/campus/index"))
    if not redirect_path.startswith("/h5/") or redirect_path.startswith("//"):
        raise ValueError("invalid OAuth redirect path")
    corp_id = os.environ.get("WECOM_CORP_ID", "").strip()
    if not corp_id:
        raise ValueError("WECOM_CORP_ID is not configured")
    state = issue_campus_wecom_state({"redirect_path": redirect_path}, identity, project_root)
    base_url = os.environ.get("APP_BASE_URL", "http://localhost:8787").rstrip("/")
    callback_url = f"{base_url}/api/campus/auth/wecom/callback?redirect=1"
    params = urlencode(
        {
            "appid": corp_id,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "snsapi_base",
            "state": state["state"],
        }
    )
    return {"authorize_url": f"https://open.weixin.qq.com/connect/oauth2/authorize?{params}#wechat_redirect"}


def get_campus_wecom_callback(query: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    ensure_demo_school_data(project_root)
    result = handle_wecom_callback(
        project_root,
        code=str(query.get("code", "")),
        state=str(query.get("state", "")),
        wecom_adapter=_wecom_adapter(project_root),
        identity_resolver=_database_wecom_identity,
    )
    _write_campus_event(project_root, EventType.CAMPUS_AUTH_CALLBACK_SUCCEEDED, result["identity"], {"session_id": result["session_id"]})
    return result


def _leave_notifier(project_root: Path, action: str, leave: dict[str, Any], extra: dict[str, Any]) -> None:
    adapter = _wecom_adapter(project_root)
    body = {
        "touser": extra.get("touser", ""),
        "msgtype": "textcard",
        "agentid": 1000001,
        "textcard": {
            "title": extra.get("title", "校园事务提醒"),
            "description": extra.get("description", ""),
            "url": extra.get("url", "https://school-saas.example.com/h5"),
            "btntxt": extra.get("btntxt", "查看"),
        },
        "safe": 0,
    }
    adapter.send_app_message(body)


def post_campus_leave(payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, LEAVE_CREATE_FIELDS)
    leave = create_leave_request(
        project_root,
        identity,
        payload,
        notifier=lambda leave_item, cls: _leave_notifier(project_root, "create", leave_item, {
            "touser": cls["head_teacher_id"].replace("user_", ""),
            "title": "请假待确认",
            "description": f"学生：{leave_item['student_name']}<br>请假时间：{leave_item['start_time']} - {leave_item['end_time']}",
        }),
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )
    return leave


def list_campus_leaves(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    return list_leave_requests(project_root, identity)


def get_campus_leave(leave_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    return get_leave_request(project_root, leave_id, identity)


def approve_campus_leave(leave_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, LEAVE_DECISION_FIELDS)
    return decide_leave_request(
        project_root,
        leave_id,
        identity,
        decision="approve",
        note=str(payload.get("note", "")),
        notifier=lambda leave_item, _: _leave_notifier(project_root, "approve", leave_item, {
            "touser": leave_item.get("student_id", ""),
            "title": "请假已批准",
            "description": f"学生：{leave_item['student_name']}<br>状态：已批准",
        }),
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def reject_campus_leave(leave_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, LEAVE_DECISION_FIELDS)
    return decide_leave_request(
        project_root,
        leave_id,
        identity,
        decision="reject",
        note=str(payload.get("note", "")),
        notifier=lambda leave_item, _: _leave_notifier(project_root, "reject", leave_item, {
            "touser": leave_item.get("student_id", ""),
            "title": "请假未通过",
            "description": f"学生：{leave_item['student_name']}<br>状态：未通过",
        }),
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def post_campus_meal_order(payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, MEAL_CREATE_FIELDS)
    return create_meal_order(
        project_root,
        identity,
        payload,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def cancel_campus_meal_order(order_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, MEAL_CANCEL_FIELDS)
    return cancel_meal_order(
        project_root,
        order_id,
        identity,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def get_campus_meal_summary(query: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    meal_date = str(query.get("date") or query.get("meal_date") or "")
    if not meal_date:
        raise ValueError("date is required")
    lock_summary = str(query.get("lock", "0")) in {"1", "true", "True"}
    return get_meal_summary(
        project_root,
        identity,
        meal_date,
        lock_summary=lock_summary,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def confirm_campus_delivery(delivery_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, DELIVERY_CONFIRM_FIELDS)
    return confirm_delivery(
        project_root,
        delivery_id,
        identity,
        payload,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def post_campus_repair(payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, REPAIR_CREATE_FIELDS)
    return create_repair_ticket(
        project_root,
        identity,
        payload,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def list_campus_repairs(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    return list_repair_tickets(project_root, identity)


def get_campus_repair(ticket_id: str, identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    return get_repair_ticket(project_root, ticket_id, identity)


def assign_campus_repair(ticket_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, REPAIR_ASSIGN_FIELDS)
    return assign_repair_ticket(
        project_root,
        ticket_id,
        identity,
        payload,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def complete_campus_repair(ticket_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, REPAIR_COMPLETE_FIELDS)
    return complete_repair_ticket(
        project_root,
        ticket_id,
        identity,
        payload,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def close_campus_repair(ticket_id: str, payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _reject_untrusted_fields(payload, REPAIR_CLOSE_FIELDS)
    return close_repair_ticket(
        project_root,
        ticket_id,
        identity,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )


def get_campus_daily_report(query: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    report_date = str(query.get("date") or "")
    if not report_date:
        raise ValueError("date is required")
    run_repair_timeouts(
        project_root,
        audit_writer=lambda event_type, actor, metadata: _write_campus_event(project_root, event_type, actor, metadata),
    )
    report = generate_daily_report(project_root, identity, report_date)
    _write_campus_event(project_root, EventType.CAMPUS_DAILY_REPORT_GENERATED, identity, {"report_id": report["report_id"], "date": report_date})
    return report
