from __future__ import annotations

import base64
import logging
import os
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

MEALBOT_SRC = Path(__file__).resolve().parents[2] / "mealbot-service" / "src"
if str(MEALBOT_SRC) not in sys.path:
    sys.path.insert(0, str(MEALBOT_SRC))

CST = timezone(timedelta(hours=8))
log = logging.getLogger("mealbot_gateway")
PARENT_ROLE = "parent_or_student_h5"
OPERATIONS_ROLES = {"admin", "super_admin", "school_admin", "campus_admin", "logistics_staff"}


def _to_json_safe(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    return obj


def _school_id(identity: dict[str, Any]) -> str:
    school_id = str(identity.get("school_id") or identity.get("campus", ""))
    if not school_id or school_id == "all":
        raise ValueError("school_id is required in identity")
    return school_id


def _require_operations_role(identity: dict[str, Any]) -> None:
    if identity.get("role") not in OPERATIONS_ROLES:
        raise ValueError("FORBIDDEN")


def _requester_wecom_userid(identity: dict[str, Any]) -> str:
    return str(identity.get("wecom_userid") or identity.get("user_id", ""))


def _require_student_access(student_id: str, identity: dict[str, Any]) -> None:
    school_id = _school_id(identity)
    if identity.get("role") in OPERATIONS_ROLES:
        return
    if identity.get("role") != PARENT_ROLE:
        raise ValueError("FORBIDDEN")
    if str(identity.get("student_id", "")) == student_id:
        return

    from app.db.repositories import students as students_repo

    requester = _requester_wecom_userid(identity)
    allowed_ids = {
        str(student["student_id"])
        for student in students_repo.get_students_by_parent_with_class(requester, school_id)
    }
    if student_id not in allowed_ids:
        raise ValueError("STUDENT_NOT_ACCESSIBLE")


def _audit_operation(
    identity: dict[str, Any],
    *,
    biz_type: str,
    biz_id: str,
    action: str,
    after: dict[str, Any] | None = None,
    actor_type: str = "user",
    metadata: dict[str, Any] | None = None,
) -> None:
    from app.db.repositories.operation_logs import write_operation_log

    write_operation_log(
        school_id=_school_id(identity),
        actor_user_id=str(identity.get("user_id", "system")),
        biz_type=biz_type,
        biz_id=biz_id,
        action=action,
        after=after,
        actor_type=actor_type,
        metadata=metadata,
    )


def _audit_rejection(identity: dict[str, Any], biz_type: str, biz_id: str, action: str) -> None:
    _audit_operation(identity, biz_type=biz_type, biz_id=biz_id, action=action, after={"status": "rejected"})


# ── GET /api/h5/students ──────────────────────────────────────────

def get_h5_students(
    query: dict[str, str],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    if identity.get("role") != PARENT_ROLE:
        raise ValueError("FORBIDDEN")

    wecom_userid = _requester_wecom_userid(identity)
    if not wecom_userid and os.environ.get("GAOKAO_ENV", "development") != "production":
        wecom_userid = query.get("wecom_userid", "")

    if not wecom_userid:
        return {"ok": True, "students": [], "next_action": "specify_wecom_userid"}

    school_id = _school_id(identity)

    from app.db.repositories import students as students_repo
    rows = students_repo.get_students_by_parent_with_class(wecom_userid, school_id)

    students = []
    for row in rows:
        students.append({
            "student_id": row["student_id"],
            "name": row["name"],
            "class_name": row.get("class_name", ""),
            "class_id": row.get("class_id", ""),
            "student_no": row.get("student_no", ""),
        })

    result: dict[str, Any] = {"ok": True, "students": students}
    if not students:
        result["next_action"] = "contact_school_admin_for_binding"
    return result


def get_h5_attachment(
    attachment_id: str,
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    del project_root
    from app.db.repositories import attachments as attachments_repo

    attachment = attachments_repo.get_attachment(attachment_id)
    if not attachment:
        raise ValueError("ATTACHMENT_NOT_FOUND")
    school_id = _school_id(identity)
    requester = identity.get("wecom_userid") or identity.get("user_id", "")
    admin_override = identity.get("role") in OPERATIONS_ROLES
    if attachment["school_id"] != school_id:
        _audit_rejection(identity, "attachment", attachment_id, "attachment.rejected_owner_mismatch")
        raise ValueError("ATTACHMENT_NOT_ACCESSIBLE")
    if not admin_override and attachment.get("created_by_wecom_userid") != requester:
        _audit_rejection(identity, "attachment", attachment_id, "attachment.rejected_owner_mismatch")
        raise ValueError("ATTACHMENT_NOT_ACCESSIBLE")
    return {
        "ok": True,
        "attachment": {
            "attachment_id": attachment["attachment_id"],
            "content_type": attachment.get("content_type"),
            "original_name": attachment.get("original_name"),
            "status": "received",
        },
    }


# ── POST /api/meal-orders ─────────────────────────────────────────

def post_mealbot_meal_order(
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.modules.meal.orders import submit_meal_order, MealLockedError
    from app.modules.meal.cutoff_policy import check_meal_cutoff, CutoffError, get_cutoff_time
    from app.modules.meal.reminder import create_meal_notification
    from app.storage.local import save_image_bytes

    school_id = _school_id(identity)

    student_id = str(payload.get("student_id", ""))
    if not student_id:
        raise ValueError("student_id is required")
    _require_student_access(student_id, identity)
    from app.db.repositories import pilot as pilot_repo
    if not pilot_repo.is_feature_enabled(school_id, "h5_submissions"):
        _audit_rejection(identity, "pilot_control", school_id, "meal_order.rejected_pilot_paused")
        return {"ok": False, "error": {"code": "PILOT_PAUSED", "message": "当前试点提交已暂停，请联系学校工作人员。"}}

    meal_date_str = str(payload.get("meal_date", ""))
    if not meal_date_str:
        raise ValueError("meal_date is required")
    meal_date = date.fromisoformat(meal_date_str)

    meal_type = str(payload.get("meal_type", "lunch"))
    action = str(payload.get("action", "order"))
    reason = str(payload.get("reason", "")) or None
    dietary_note = str(payload.get("dietary_note", "")) or None
    class_id = str(payload.get("class_id", ""))

    wecom_userid = identity.get("wecom_userid") or identity.get("user_id", "")
    is_dev = os.environ.get("GAOKAO_ENV", "development") != "production"
    submitted_by = str(wecom_userid or (payload.get("submitted_by_wecom_userid", "") if is_dev else "")) or None

    admin_override = identity.get("role") in OPERATIONS_ROLES
    attachment_id = str(payload.get("attachment_id", "")).strip()
    linked_attachment = None
    if attachment_id:
        from app.db.repositories import attachments as attachments_repo
        linked_attachment = attachments_repo.get_attachment(attachment_id)
        if not linked_attachment or linked_attachment["school_id"] != school_id:
            _audit_rejection(identity, "attachment", attachment_id, "attachment.rejected_owner_mismatch")
            raise ValueError("ATTACHMENT_NOT_ACCESSIBLE")
        if not admin_override and linked_attachment.get("created_by_wecom_userid") != submitted_by:
            _audit_rejection(identity, "attachment", attachment_id, "attachment.rejected_owner_mismatch")
            raise ValueError("ATTACHMENT_NOT_ACCESSIBLE")
        if linked_attachment.get("biz_type") == "meal_order":
            _audit_rejection(identity, "attachment", attachment_id, "attachment.rejected_already_used")
            raise ValueError("ATTACHMENT_ALREADY_LINKED")

    try:
        check_meal_cutoff(meal_type, meal_date)
    except CutoffError as ce:
        return {
            "ok": False,
            "error": {"code": ce.code, "message": f"{meal_type}订退餐已截止", "cutoff_at": get_cutoff_time(meal_type)},
        }

    try:
        order = submit_meal_order(
            school_id=school_id, student_id=student_id, class_id=class_id,
            meal_date=meal_date, meal_type=meal_type, action=action,
            reason=reason, dietary_note=dietary_note,
            submitted_by_wecom_userid=submitted_by,
            admin_override=admin_override and payload.get("admin_override", False),
        )
    except MealLockedError:
        _audit_rejection(identity, "meal_order", student_id, "meal_order.rejected_locked")
        return {
            "ok": False,
            "error": {"code": "MEAL_LOCKED", "message": "该餐次已锁单，无法继续订餐或退餐。",
                      "meal_date": str(meal_date), "meal_type": meal_type},
        }

    attachment = None
    photo_bytes = payload.get("photo_bytes")
    if photo_bytes and isinstance(photo_bytes, bytes) and len(photo_bytes) > 0:
        attachment = save_image_bytes(
            file_bytes=photo_bytes,
            original_name=str(payload.get("photo_filename", "upload.jpg")),
            content_type=str(payload.get("photo_content_type", "image/jpeg")),
            school_id=school_id,
        )
    elif payload.get("photo_base64"):
        try:
            file_bytes = base64.b64decode(str(payload["photo_base64"]))
        except Exception:
            raise ValueError("INVALID_BASE64")
        attachment = save_image_bytes(
            file_bytes=file_bytes,
            original_name=str(payload.get("photo_filename", "upload.jpg")),
            content_type=str(payload.get("photo_content_type", "image/jpeg")),
            school_id=school_id,
        )

    if attachment:
        from app.db.repositories import attachments as attachments_repo
        from uuid import uuid4
        new_attachment = attachments_repo.create_attachment({
            "attachment_id": f"ATT-{uuid4().hex[:12]}",
            "school_id": school_id, "source": attachment.get("source", "h5_upload"),
            "biz_type": "meal_order", "biz_id": order["order_id"],
            "file_path": attachment["file_path"],
            "original_name": attachment.get("original_name"),
            "content_type": attachment.get("content_type"),
            "size_bytes": attachment.get("size_bytes"),
            "sha256": attachment.get("sha256"),
            "created_by_wecom_userid": submitted_by,
        })
        _audit_operation(
            identity, biz_type="attachment", biz_id=str(new_attachment["attachment_id"]),
            action="attachment.created", after={"order_id": order["order_id"], "source": "h5_upload"},
        )
    elif linked_attachment:
        from app.db.repositories import attachments as attachments_repo
        linked = attachments_repo.link_attachment_to_meal_order(attachment_id, order["order_id"])
        if not linked:
            _audit_rejection(identity, "attachment", attachment_id, "attachment.rejected_already_used")
            raise ValueError("ATTACHMENT_ALREADY_LINKED")
        _audit_operation(
            identity, biz_type="attachment", biz_id=attachment_id,
            action="attachment.linked", after={"order_id": order["order_id"]},
        )

    try:
        create_meal_notification(
            school_id=school_id, order_id=order["order_id"],
            student_id=student_id, meal_date=meal_date_str,
            meal_type=meal_type, action=action,
        )
    except Exception:
        log.warning("reminder task creation failed", exc_info=True)

    _audit_operation(
        identity,
        biz_type="meal_order",
        biz_id=str(order["order_id"]),
        action="meal_order.created",
        after={"meal_date": meal_date_str, "meal_type": meal_type, "action": action},
    )
    if admin_override and payload.get("admin_override", False):
        _audit_operation(
            identity, biz_type="meal_order", biz_id=str(order["order_id"]),
            action="meal_order.admin_override", after={"reason": "submit_after_lock"},
        )
    return _to_json_safe({"ok": True, "order": order})


# ── GET /api/meal-orders ──────────────────────────────────────────

def get_mealbot_orders(
    query: dict[str, str],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.modules.meal.orders import list_student_orders

    student_id = query.get("student_id", "")
    if not student_id:
        raise ValueError("student_id is required")
    _require_student_access(student_id, identity)
    meal_date_str = query.get("meal_date", "")
    meal_date = date.fromisoformat(meal_date_str) if meal_date_str else None
    orders = list_student_orders(student_id, meal_date)
    return _to_json_safe({"orders": orders})


# ── POST /api/meal-orders/{id}/cancel ─────────────────────────────

def post_mealbot_meal_order_cancel(
    order_id: str,
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.db.repositories import meal_orders as orders_repo
    from app.modules.meal.orders import cancel_meal_order

    order = orders_repo.get_order(order_id)
    if not order:
        raise ValueError("ORDER_NOT_FOUND")
    if str(order.get("school_id", "")) != _school_id(identity):
        raise ValueError("ORDER_NOT_ACCESSIBLE")
    _require_student_access(str(order.get("student_id", "")), identity)

    order = cancel_meal_order(order_id)
    if not order:
        raise ValueError("ORDER_NOT_FOUND")
    _audit_operation(
        identity,
        biz_type="meal_order",
        biz_id=order_id,
        action="meal_order.cancelled",
        after={"status": "cancelled"},
    )
    return _to_json_safe({"ok": True, "order": order})


# ── POST /api/meal-locks ──────────────────────────────────────────

def post_mealbot_lock(
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.modules.meal.orders import lock_meal

    _require_operations_role(identity)
    school_id = _school_id(identity)

    meal_date_str = str(payload.get("meal_date", ""))
    if not meal_date_str:
        raise ValueError("meal_date is required")
    meal_date = date.fromisoformat(meal_date_str)

    meal_type = str(payload.get("meal_type", "lunch"))
    locked_by = str(payload.get("locked_by", identity.get("user_id", "system")))

    result = lock_meal(school_id=school_id, meal_date=meal_date, meal_type=meal_type, locked_by=locked_by)
    lock = result.get("lock", {})
    _audit_operation(
        identity,
        biz_type="meal_lock",
        biz_id=str(lock.get("lock_id", "")),
        action="meal_lock.updated" if result.get("message") == "already_locked" else "meal_lock.created",
        after={"meal_date": meal_date_str, "meal_type": meal_type, "locked_count": result.get("locked_count", 0)},
    )
    return _to_json_safe({"ok": True, **result})


# ── GET /api/logistics/meal-summary ───────────────────────────────

def get_logistics_meal_summary(
    query: dict[str, str],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.modules.meal.orders import get_logistics_summary

    _require_operations_role(identity)
    school_id = _school_id(identity)

    meal_date_str = query.get("meal_date", "")
    if not meal_date_str:
        return {"ok": False, "error": "meal_date is required"}
    meal_date = date.fromisoformat(meal_date_str)

    meal_type = query.get("meal_type") or None
    result = get_logistics_summary(school_id, meal_date, meal_type)
    return _to_json_safe({"ok": True, **result})


# ── POST /api/vendor-confirmations ────────────────────────────────

def post_vendor_confirmation(
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.modules.meal.orders import generate_vendor_confirmation

    _require_operations_role(identity)
    school_id = _school_id(identity)

    lock_id = str(payload.get("meal_lock_id", ""))
    if not lock_id:
        raise ValueError("meal_lock_id is required")

    vendor_name = str(payload.get("vendor_name", ""))
    vendor_contact = str(payload.get("vendor_contact", ""))
    expires_in = int(payload.get("expires_in_minutes", 180))

    result = generate_vendor_confirmation(
        lock_id=lock_id, school_id=school_id,
        vendor_name=vendor_name, vendor_contact=vendor_contact,
        expires_in_minutes=expires_in,
    )
    confirmation = result.get("confirmation", {})
    _audit_operation(
        identity,
        biz_type="vendor_confirmation",
        biz_id=str(confirmation.get("confirmation_id", "")),
        action="vendor_confirmation.created",
        after={"meal_lock_id": lock_id},
    )
    return _to_json_safe({"ok": True, **result})


# ── POST /api/vendor-confirmations/confirm ────────────────────────

def post_vendor_confirm_action(
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.modules.meal.orders import confirm_vendor

    token = str(payload.get("token", ""))
    if not token:
        raise ValueError("vendor token is required")

    action = str(payload.get("action", "confirmed"))
    confirmed_by = str(payload.get("confirmed_by", ""))
    abnormal_note = str(payload.get("abnormal_note", ""))

    result = confirm_vendor(token=token, action=action, confirmed_by=confirmed_by, abnormal_note=abnormal_note)
    confirmation = result.get("confirmation") or {}
    from app.db.repositories.operation_logs import write_operation_log

    write_operation_log(
        school_id=str(confirmation.get("school_id", "")),
        actor_user_id="vendor_link",
        biz_type="vendor_confirmation",
        biz_id=str(confirmation.get("confirmation_id", "")),
        action=f"vendor_confirmation.{action}",
        actor_type="vendor_link",
        after={"status": confirmation.get("status", "")},
    )
    return _to_json_safe(result)


# ── GET /vendor/confirm ───────────────────────────────────────────

def get_vendor_confirm_page(
    query: dict[str, str],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.modules.meal.orders import get_vendor_confirmation_info

    token = query.get("t", "")
    if not token:
        return {"ok": False, "error": {"code": "MISSING_TOKEN", "message": "缺少确认令牌"}}

    info = get_vendor_confirmation_info(token)
    return _to_json_safe(info)


# ── POST /api/scheduler/run-due-reminders ──────────────────────────

def post_scheduler_run_due_reminders(
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    from app.services.reminder_service import process_due_reminders

    _require_operations_role(identity)
    worker_id = str(payload.get("worker_id", "api_manual"))
    counts = process_due_reminders(worker_id)
    return {"ok": True, **counts}


def get_wecom_message_callback(query: dict[str, str], project_root: Path) -> str:
    del project_root
    from app.modules.wecom.callback import verify_callback_url

    return verify_callback_url(query)


def post_wecom_message_callback(query: dict[str, str], raw_xml: str, project_root: Path) -> str:
    from app.modules.wecom.callback import receive_callback_message

    receive_callback_message(query, raw_xml, project_root)
    return "success"


def post_wecom_process_media_downloads(
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    _require_operations_role(identity)
    from app.modules.wecom.media_download import process_pending_media_downloads

    limit = int(payload.get("limit", 20))
    return {"ok": True, **process_pending_media_downloads(project_root, limit=limit, school_id=_school_id(identity))}


def get_pilot_status(
    query: dict[str, str],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    del project_root
    _require_operations_role(identity)
    school_id = _school_id(identity)
    requested_school = query.get("school_id", "")
    if requested_school and requested_school != school_id and identity.get("role") not in {"admin", "super_admin"}:
        raise ValueError("SCHOOL_NOT_ACCESSIBLE")
    school_id = requested_school or school_id
    report_date = date.fromisoformat(query.get("date", date.today().isoformat()))
    from app.modules.pilot.service import pilot_status

    return _to_json_safe(pilot_status(school_id, report_date))


def post_pilot_runtime_control(
    action: str,
    payload: dict[str, Any],
    identity: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    del project_root
    _require_operations_role(identity)
    school_id = _school_id(identity)
    features = payload.get("features") or ["h5_submissions", "reminder_worker", "wecom_media_worker"]
    if not isinstance(features, list):
        raise ValueError("features must be a list")
    from app.modules.pilot.service import set_runtime_state

    controls = set_runtime_state(
        school_id,
        [str(feature) for feature in features],
        action == "resume",
        str(identity.get("user_id", "pilot_api")),
    )
    return _to_json_safe({"ok": True, "school_id": school_id, "controls": controls})
