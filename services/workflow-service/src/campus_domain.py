from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


LeaveNotifier = Callable[[dict[str, Any], dict[str, Any]], None]
ReminderWriter = Callable[[dict[str, Any]], dict[str, Any]]
AuditWriter = Callable[[str, dict[str, Any], dict[str, Any]], None]
AiSuggester = Callable[[str], dict[str, Any]]


ROLE_PARENT = "parent_or_student_h5"
ROLE_VENDOR = "vendor_link_user"
ROLE_HEAD_TEACHER = "head_teacher"
ROLE_ACADEMIC = "academic_staff"
ROLE_LOGISTICS = "logistics_staff"
ROLE_REPAIR = "repair_assignee"
ROLE_SCHOOL_ADMIN = "school_admin"
ROLE_SUPER_ADMIN = "super_admin"

LEAVE_APPROVER_ROLES = {ROLE_HEAD_TEACHER, ROLE_ACADEMIC, ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}
REPAIR_OPERATOR_ROLES = {ROLE_LOGISTICS, ROLE_REPAIR, ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}
ADMINISTRATIVE_ROLES = {ROLE_ACADEMIC, ROLE_LOGISTICS, ROLE_HEAD_TEACHER, ROLE_REPAIR, ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _campus_root(project_root: Path) -> Path:
    base = project_root / "data" / "campus"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _entity_dir(project_root: Path, entity: str) -> Path:
    path = _campus_root(project_root) / entity
    path.mkdir(parents=True, exist_ok=True)
    return path


def _entity_path(project_root: Path, entity: str, item_id: str) -> Path:
    return _entity_dir(project_root, entity) / f"{item_id}.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload.setdefault("updated_at", _now_iso())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_entity(project_root: Path, entity: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_entity_dir(project_root, entity).glob("*.json")):
        data = _load_json(path)
        if data:
            items.append(data)
    return items


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 7:
        return "***"
    return f"{digits[:3]}****{digits[-4:]}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(f"campus::{token}".encode("utf-8")).hexdigest()


def ensure_demo_school_data(project_root: Path) -> None:
    schools = _list_entity(project_root, "schools")
    if schools:
        return

    school = {
        "school_id": "school_demo",
        "name": "演示校园",
        "status": "active",
        "wecom_corp_id": "demo-corp",
        "wecom_agent_id": "1000001",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    cls = {
        "class_id": "class_g7_1",
        "school_id": school["school_id"],
        "grade": "七年级",
        "name": "七年级1班",
        "head_teacher_id": "user_teacher_001",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    teacher = {
        "user_id": "user_teacher_001",
        "school_id": school["school_id"],
        "wecom_userid": "teacher_001",
        "name": "班主任李老师",
        "role": ROLE_HEAD_TEACHER,
        "class_ids": [cls["class_id"]],
        "status": "active",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    academic = {
        "user_id": "user_academic_001",
        "school_id": school["school_id"],
        "wecom_userid": "academic_001",
        "name": "教务王老师",
        "role": ROLE_ACADEMIC,
        "class_ids": [],
        "status": "active",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    logistics = {
        "user_id": "user_logistics_001",
        "school_id": school["school_id"],
        "wecom_userid": "logistics_001",
        "name": "后勤张老师",
        "role": ROLE_LOGISTICS,
        "class_ids": [],
        "status": "active",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    repair_assignee = {
        "user_id": "user_repair_001",
        "school_id": school["school_id"],
        "wecom_userid": "repair_001",
        "name": "维修陈师傅",
        "role": ROLE_REPAIR,
        "class_ids": [],
        "status": "active",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    student = {
        "student_id": "student_demo_001",
        "school_id": school["school_id"],
        "class_id": cls["class_id"],
        "name": "张小明",
        "student_no": "2026001",
        "parent_name": "张家长",
        "parent_mobile_hash": _hash_token("13800138000"),
        "parent_mobile_mask": _mask_phone("13800138000"),
        "parent_userid": "parent_demo_001",
        "status": "active",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    for entity, item, item_id in (
        ("schools", school, school["school_id"]),
        ("classes", cls, cls["class_id"]),
        ("users", teacher, teacher["user_id"]),
        ("users", academic, academic["user_id"]),
        ("users", logistics, logistics["user_id"]),
        ("users", repair_assignee, repair_assignee["user_id"]),
        ("students", student, student["student_id"]),
    ):
        _save_json(_entity_path(project_root, entity, item_id), item)


def _get_entity(project_root: Path, entity: str, item_id: str, label: str) -> dict[str, Any]:
    data = _load_json(_entity_path(project_root, entity, item_id))
    if data is None:
        raise ValueError(f"{label} not found: {item_id}")
    return data


def _find_user_by_wecom(project_root: Path, wecom_userid: str) -> dict[str, Any] | None:
    for user in _list_entity(project_root, "users"):
        if user.get("wecom_userid") == wecom_userid:
            return user
    return None


def _find_class(project_root: Path, class_id: str) -> dict[str, Any]:
    return _get_entity(project_root, "classes", class_id, "class")


def _find_student(project_root: Path, student_id: str) -> dict[str, Any]:
    return _get_entity(project_root, "students", student_id, "student")


def _find_user(project_root: Path, user_id: str) -> dict[str, Any]:
    return _get_entity(project_root, "users", user_id, "user")


def create_wecom_mapping_state(project_root: Path, redirect_path: str = "/h5") -> dict[str, Any]:
    state_id = secrets.token_urlsafe(18)
    payload = {
        "state": state_id,
        "redirect_path": redirect_path,
        "expires_at": (_now() + timedelta(minutes=10)).isoformat(),
        "created_at": _now_iso(),
    }
    _save_json(_entity_path(project_root, "wecom_states", state_id), payload)
    return payload


def consume_wecom_state(project_root: Path, state_id: str) -> dict[str, Any]:
    payload = _get_entity(project_root, "wecom_states", state_id, "oauth state")
    expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    if expires_at < _now():
        raise ValueError("oauth state expired")
    _entity_path(project_root, "wecom_states", state_id).unlink(missing_ok=True)
    return payload


def resolve_local_identity_for_wecom(project_root: Path, wecom_userid: str) -> dict[str, Any]:
    ensure_demo_school_data(project_root)
    user = _find_user_by_wecom(project_root, wecom_userid)
    if not user:
        raise ValueError(f"wecom user not mapped: {wecom_userid}")
    return {
        "user_id": user["user_id"],
        "role": user["role"],
        "campus": user.get("school_id", "school_demo"),
        "auth_level": "wecom_oauth",
        "school_id": user.get("school_id", "school_demo"),
        "class_ids": user.get("class_ids", []),
        "wecom_userid": wecom_userid,
    }


def issue_vendor_token(project_root: Path, delivery_id: str, vendor_name: str = "演示供应商") -> dict[str, Any]:
    token = secrets.token_urlsafe(24)
    payload = {
        "token_hash": _hash_token(token),
        "delivery_id": delivery_id,
        "vendor_name": vendor_name,
        "created_at": _now_iso(),
        "expires_at": (_now() + timedelta(days=1)).isoformat(),
    }
    _save_json(_entity_path(project_root, "vendor_tokens", delivery_id), payload)
    return {"token": token, **payload}


def verify_vendor_token(project_root: Path, delivery_id: str, token: str) -> dict[str, Any]:
    payload = _get_entity(project_root, "vendor_tokens", delivery_id, "vendor token")
    if payload.get("token_hash") != _hash_token(token):
        raise ValueError("invalid vendor token")
    expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    if expires_at < _now():
        raise ValueError("vendor token expired")
    return payload


def _visible_class_ids(identity: dict[str, Any]) -> set[str]:
    values = identity.get("class_ids", [])
    if isinstance(values, list):
        return {str(value) for value in values}
    if isinstance(values, str) and values:
        return {values}
    return set()


def _visible_school(identity: dict[str, Any]) -> str:
    return str(identity.get("school_id") or identity.get("campus") or "school_demo")


def _ensure_parent_scope(identity: dict[str, Any], student: dict[str, Any]) -> None:
    if identity.get("role") != ROLE_PARENT:
        return
    if identity.get("student_id") and identity.get("student_id") != student.get("student_id"):
        raise ValueError("student scope mismatch")
    school_id = _visible_school(identity)
    if school_id != str(student.get("school_id")):
        raise ValueError("school scope mismatch")


def _ensure_staff_can_view(identity: dict[str, Any], class_id: str, school_id: str) -> None:
    role = identity.get("role")
    if role in {ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}:
        return
    if role == ROLE_HEAD_TEACHER and class_id in _visible_class_ids(identity):
        return
    if role in {ROLE_ACADEMIC, ROLE_LOGISTICS, ROLE_REPAIR} and school_id == _visible_school(identity):
        return
    raise ValueError("campus record not accessible")


def _ensure_leave_visible(identity: dict[str, Any], leave: dict[str, Any]) -> None:
    if identity.get("role") == ROLE_PARENT:
        if identity.get("student_id") != leave.get("student_id"):
            raise ValueError("leave request not accessible")
        return
    _ensure_staff_can_view(identity, str(leave.get("class_id", "")), str(leave.get("school_id", "")))


def _ensure_repair_visible(identity: dict[str, Any], repair: dict[str, Any]) -> None:
    role = identity.get("role")
    if role in {ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN, ROLE_LOGISTICS}:
        return
    if role == ROLE_REPAIR and repair.get("assignee_id") == identity.get("user_id"):
        return
    if role == ROLE_HEAD_TEACHER and repair.get("class_id") in _visible_class_ids(identity):
        return
    if role == ROLE_PARENT and repair.get("created_by") == identity.get("user_id"):
        return
    raise ValueError("repair ticket not accessible")


def _create_reminder(project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    reminder_id = payload.get("reminder_id") or _new_id("reminder")
    reminder = {
        "reminder_id": reminder_id,
        "status": payload.get("status", "pending"),
        "biz_type": payload["biz_type"],
        "biz_id": payload["biz_id"],
        "receiver_type": payload["receiver_type"],
        "receiver_id": payload["receiver_id"],
        "channel": payload.get("channel", "wecom_app"),
        "template_id": payload.get("template_id", "default"),
        "payload_json": payload.get("payload_json", {}),
        "scheduled_at": payload.get("scheduled_at", _now_iso()),
        "retry_count": payload.get("retry_count", 0),
        "school_id": payload.get("school_id", "school_demo"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _save_json(_entity_path(project_root, "reminder_tasks", reminder_id), reminder)
    return reminder


def _append_timeline(record: dict[str, Any], action: str, actor_id: str, metadata: dict[str, Any] | None = None) -> None:
    timeline = record.setdefault("timeline", [])
    timeline.append({
        "event_id": _new_id("evt"),
        "action": action,
        "actor_id": actor_id,
        "metadata": metadata or {},
        "created_at": _now_iso(),
    })


def seed_default_delivery_token(project_root: Path, delivery: dict[str, Any]) -> None:
    token_path = _entity_path(project_root, "vendor_tokens", str(delivery["delivery_id"]))
    if token_path.exists():
        return
    issue_vendor_token(project_root, str(delivery["delivery_id"]))


def create_leave_request(
    project_root: Path,
    identity: dict[str, Any],
    payload: dict[str, Any],
    *,
    notifier: LeaveNotifier | None = None,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    ensure_demo_school_data(project_root)
    if identity.get("role") != ROLE_PARENT:
        raise ValueError("only parent_or_student_h5 can create leave requests")
    student_id = str(payload.get("student_id", ""))
    if not student_id:
        raise ValueError("student_id is required")
    student = _find_student(project_root, student_id)
    _ensure_parent_scope(identity, student)
    leave_id = _new_id("leave")
    leave = {
        "leave_id": leave_id,
        "school_id": student["school_id"],
        "student_id": student_id,
        "class_id": student["class_id"],
        "type": payload.get("type", "personal"),
        "start_time": payload.get("start_time"),
        "end_time": payload.get("end_time"),
        "reason": payload.get("reason", ""),
        "status": "pending",
        "approver_id": None,
        "approved_at": None,
        "decision_note": "",
        "attachments_json": payload.get("attachments_json", []),
        "created_by": identity.get("user_id"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "student_name": student["name"],
        "parent_mobile_mask": student.get("parent_mobile_mask"),
    }
    _append_timeline(leave, "leave.created", str(identity.get("user_id", "anonymous")), {"reason": leave["reason"]})
    _save_json(_entity_path(project_root, "leave_requests", leave_id), leave)

    cls = _find_class(project_root, str(student["class_id"]))
    reminder = _create_reminder(project_root, {
        "biz_type": "leave_request",
        "biz_id": leave_id,
        "receiver_type": "user",
        "receiver_id": cls["head_teacher_id"],
        "channel": "wecom_app",
        "template_id": "leave_pending_approval",
        "payload_json": {"leave_id": leave_id, "student_name": student["name"]},
        "school_id": student["school_id"],
    })
    leave["reminder_task_ids"] = [reminder["reminder_id"]]
    _save_json(_entity_path(project_root, "leave_requests", leave_id), leave)

    if notifier:
        notifier(leave, cls)
    if audit_writer:
        audit_writer("campus.leave.created", identity, {"leave_id": leave_id, "student_id": student_id})
    return leave


def list_leave_requests(project_root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    ensure_demo_school_data(project_root)
    items: list[dict[str, Any]] = []
    for leave in _list_entity(project_root, "leave_requests"):
        try:
            _ensure_leave_visible(identity, leave)
        except ValueError:
            continue
        items.append(leave)
    items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"items": items, "total": len(items)}


def get_leave_request(project_root: Path, leave_id: str, identity: dict[str, Any]) -> dict[str, Any]:
    leave = _get_entity(project_root, "leave_requests", leave_id, "leave request")
    _ensure_leave_visible(identity, leave)
    return leave


def decide_leave_request(
    project_root: Path,
    leave_id: str,
    identity: dict[str, Any],
    *,
    decision: str,
    note: str = "",
    notifier: LeaveNotifier | None = None,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    if identity.get("role") not in LEAVE_APPROVER_ROLES:
        raise ValueError("leave approval denied")
    leave = _get_entity(project_root, "leave_requests", leave_id, "leave request")
    _ensure_staff_can_view(identity, str(leave["class_id"]), str(leave["school_id"]))
    if leave.get("status") in {"approved", "rejected"}:
        return leave
    leave["status"] = "approved" if decision == "approve" else "rejected"
    leave["approver_id"] = identity.get("user_id")
    leave["approved_at"] = _now_iso()
    leave["decision_note"] = note
    _append_timeline(leave, f"leave.{leave['status']}", str(identity.get("user_id", "system")), {"note": note})
    _save_json(_entity_path(project_root, "leave_requests", leave_id), leave)
    if notifier:
        notifier(leave, {"decision": decision})
    if audit_writer:
        audit_writer(f"campus.leave.{leave['status']}", identity, {"leave_id": leave_id, "decision_note": note})
    return leave


def create_meal_order(
    project_root: Path,
    identity: dict[str, Any],
    payload: dict[str, Any],
    *,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    if identity.get("role") != ROLE_PARENT:
        raise ValueError("only parent_or_student_h5 can create meal orders")
    student = _find_student(project_root, str(payload.get("student_id", "")))
    _ensure_parent_scope(identity, student)
    order_id = _new_id("meal")
    order = {
        "order_id": order_id,
        "school_id": student["school_id"],
        "student_id": student["student_id"],
        "class_id": student["class_id"],
        "meal_date": payload.get("meal_date"),
        "meal_type": payload.get("meal_type", "lunch"),
        "action": payload.get("action", "order"),
        "dietary_note": payload.get("dietary_note", ""),
        "status": "submitted",
        "locked_at": None,
        "created_by": identity.get("user_id"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "student_name": student["name"],
    }
    _append_timeline(order, "meal_order.created", str(identity.get("user_id", "anonymous")), {})
    _save_json(_entity_path(project_root, "meal_orders", order_id), order)
    if audit_writer:
        audit_writer("campus.meal.created", identity, {"order_id": order_id, "meal_date": order["meal_date"]})
    return order


def cancel_meal_order(
    project_root: Path,
    order_id: str,
    identity: dict[str, Any],
    *,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    order = _get_entity(project_root, "meal_orders", order_id, "meal order")
    if identity.get("role") != ROLE_PARENT or identity.get("student_id") != order.get("student_id"):
        raise ValueError("meal order not accessible")
    if order.get("status") == "locked":
        raise ValueError("meal order already locked")
    if order.get("status") == "cancelled":
        return order
    order["status"] = "cancelled"
    _append_timeline(order, "meal_order.cancelled", str(identity.get("user_id", "anonymous")), {})
    _save_json(_entity_path(project_root, "meal_orders", order_id), order)
    if audit_writer:
        audit_writer("campus.meal.cancelled", identity, {"order_id": order_id})
    return order


def get_meal_summary(
    project_root: Path,
    identity: dict[str, Any],
    meal_date: str,
    *,
    lock_summary: bool = False,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    if identity.get("role") not in {ROLE_LOGISTICS, ROLE_ACADEMIC, ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}:
        raise ValueError("meal summary access denied")
    ensure_demo_school_data(project_root)
    active_orders = [
        order for order in _list_entity(project_root, "meal_orders")
        if order.get("meal_date") == meal_date and order.get("status") != "cancelled"
    ]
    counts = Counter(str(order.get("meal_type", "lunch")) for order in active_orders)
    total_count = len(active_orders)
    special_count = sum(1 for order in active_orders if order.get("dietary_note"))
    delivery_id = f"delivery_{meal_date.replace('-', '')}"
    delivery_path = _entity_path(project_root, "delivery_confirmations", delivery_id)
    delivery = _load_json(delivery_path) or {
        "delivery_id": delivery_id,
        "school_id": _visible_school(identity),
        "meal_date": meal_date,
        "meal_type": "lunch",
        "vendor_id": "vendor_demo",
        "status": "pending",
        "confirmed_at": None,
        "token_hash": "",
        "created_at": _now_iso(),
    }
    delivery["total_count"] = total_count
    delivery["special_count"] = special_count
    delivery["meal_breakdown"] = dict(counts)
    if lock_summary and delivery.get("status") == "pending":
        for order in active_orders:
            if order.get("status") == "submitted":
                order["status"] = "locked"
                order["locked_at"] = _now_iso()
                _append_timeline(order, "meal_order.locked", str(identity.get("user_id", "system")), {})
                _save_json(_entity_path(project_root, "meal_orders", str(order["order_id"])), order)
        delivery["status"] = "locked"
        _append_timeline(delivery, "delivery.locked", str(identity.get("user_id", "system")), {"meal_date": meal_date})
    _save_json(delivery_path, delivery)
    seed_default_delivery_token(project_root, delivery)
    if audit_writer:
        audit_writer("campus.meal.summary", identity, {"meal_date": meal_date, "total_count": total_count})
    return {"meal_date": meal_date, "total_count": total_count, "special_count": special_count, "delivery": delivery, "items": active_orders}


def confirm_delivery(
    project_root: Path,
    delivery_id: str,
    identity: dict[str, Any],
    payload: dict[str, Any],
    *,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    delivery = _get_entity(project_root, "delivery_confirmations", delivery_id, "delivery confirmation")
    role = identity.get("role")
    if role == ROLE_VENDOR:
        verify_vendor_token(project_root, delivery_id, str(payload.get("token", "")))
    elif role not in {ROLE_LOGISTICS, ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}:
        raise ValueError("delivery confirmation denied")
    delivery["status"] = "confirmed"
    delivery["confirmed_at"] = _now_iso()
    delivery["confirmed_by"] = identity.get("user_id", "vendor_link")
    delivery["note"] = payload.get("note", "")
    _append_timeline(delivery, "delivery.confirmed", str(identity.get("user_id", "vendor_link")), {"note": delivery["note"]})
    _save_json(_entity_path(project_root, "delivery_confirmations", delivery_id), delivery)
    if audit_writer:
        audit_writer("campus.delivery.confirmed", identity, {"delivery_id": delivery_id})
    return delivery


def suggest_repair_classification(description: str) -> dict[str, Any]:
    text = description.lower()
    category = "general"
    priority = "medium"
    if any(token in text for token in ("漏水", "water", "pipe", "洗手间")):
        category = "plumbing"
        priority = "high"
    elif any(token in text for token in ("电", "灯", "power", "空调", "风扇")):
        category = "electrical"
    elif any(token in text for token in ("门", "窗", "desk", "课桌", "玻璃")):
        category = "facility"
    if any(token in text for token in ("安全", "危险", "漏电", "火", "冒烟")):
        priority = "urgent"
    return {"category": category, "priority": priority, "source": "rule_sidecar"}


def create_repair_ticket(
    project_root: Path,
    identity: dict[str, Any],
    payload: dict[str, Any],
    *,
    ai_suggester: AiSuggester | None = None,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    ensure_demo_school_data(project_root)
    school_id = _visible_school(identity)
    class_id = str(payload.get("class_id") or next(iter(_visible_class_ids(identity) or {""}), ""))
    try:
        suggestion = (ai_suggester or suggest_repair_classification)(str(payload.get("description", "")))
    except Exception as exc:
        suggestion = {
            "category": payload.get("category", "general"),
            "priority": payload.get("priority", "medium"),
            "source": "fallback_sidecar",
            "error": str(exc),
        }
    ticket_id = _new_id("repair")
    ticket = {
        "ticket_id": ticket_id,
        "school_id": school_id,
        "class_id": class_id,
        "location_type": payload.get("location_type", "classroom"),
        "location_detail": payload.get("location_detail", ""),
        "category": payload.get("category") or suggestion.get("category", "general"),
        "priority": payload.get("priority") or suggestion.get("priority", "medium"),
        "ai_suggestion": suggestion,
        "description": payload.get("description", ""),
        "status": "pending",
        "assignee_id": None,
        "deadline_at": payload.get("deadline_at") or (_now() + timedelta(hours=12)).isoformat(),
        "completed_at": None,
        "images_json": payload.get("images_json", []),
        "created_by": identity.get("user_id"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _append_timeline(ticket, "repair.created", str(identity.get("user_id", "anonymous")), {"ai_suggestion": suggestion})
    _save_json(_entity_path(project_root, "repair_tickets", ticket_id), ticket)
    _create_reminder(project_root, {
        "biz_type": "repair_ticket",
        "biz_id": ticket_id,
        "receiver_type": "role",
        "receiver_id": ROLE_LOGISTICS,
        "channel": "wecom_app",
        "template_id": "repair_new",
        "payload_json": {"ticket_id": ticket_id, "priority": ticket["priority"]},
        "school_id": school_id,
    })
    if audit_writer:
        audit_writer("campus.repair.created", identity, {"ticket_id": ticket_id, "category": ticket["category"]})
    return ticket


def list_repair_tickets(project_root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    ensure_demo_school_data(project_root)
    items: list[dict[str, Any]] = []
    for repair in _list_entity(project_root, "repair_tickets"):
        try:
            _ensure_repair_visible(identity, repair)
        except ValueError:
            continue
        items.append(repair)
    items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"items": items, "total": len(items)}


def get_repair_ticket(project_root: Path, ticket_id: str, identity: dict[str, Any]) -> dict[str, Any]:
    ticket = _get_entity(project_root, "repair_tickets", ticket_id, "repair ticket")
    _ensure_repair_visible(identity, ticket)
    return ticket


def assign_repair_ticket(
    project_root: Path,
    ticket_id: str,
    identity: dict[str, Any],
    payload: dict[str, Any],
    *,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    if identity.get("role") not in {ROLE_LOGISTICS, ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}:
        raise ValueError("repair assignment denied")
    ticket = _get_entity(project_root, "repair_tickets", ticket_id, "repair ticket")
    assignee_id = str(payload.get("assignee_id", ""))
    if not assignee_id:
        raise ValueError("assignee_id is required")
    _find_user(project_root, assignee_id)
    ticket["assignee_id"] = assignee_id
    ticket["status"] = "processing"
    _append_timeline(ticket, "repair.assigned", str(identity.get("user_id", "system")), {"assignee_id": assignee_id})
    _save_json(_entity_path(project_root, "repair_tickets", ticket_id), ticket)
    if audit_writer:
        audit_writer("campus.repair.assigned", identity, {"ticket_id": ticket_id, "assignee_id": assignee_id})
    return ticket


def complete_repair_ticket(
    project_root: Path,
    ticket_id: str,
    identity: dict[str, Any],
    payload: dict[str, Any],
    *,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    ticket = _get_entity(project_root, "repair_tickets", ticket_id, "repair ticket")
    if identity.get("role") not in REPAIR_OPERATOR_ROLES and ticket.get("assignee_id") != identity.get("user_id"):
        raise ValueError("repair completion denied")
    ticket["status"] = "completed"
    ticket["completed_at"] = _now_iso()
    ticket["result_note"] = payload.get("result_note", "")
    ticket["result_images_json"] = payload.get("result_images_json", [])
    _append_timeline(ticket, "repair.completed", str(identity.get("user_id", "system")), {"result_note": ticket["result_note"]})
    _save_json(_entity_path(project_root, "repair_tickets", ticket_id), ticket)
    if audit_writer:
        audit_writer("campus.repair.completed", identity, {"ticket_id": ticket_id})
    return ticket


def close_repair_ticket(
    project_root: Path,
    ticket_id: str,
    identity: dict[str, Any],
    *,
    audit_writer: AuditWriter | None = None,
) -> dict[str, Any]:
    ticket = _get_entity(project_root, "repair_tickets", ticket_id, "repair ticket")
    if identity.get("role") not in {ROLE_HEAD_TEACHER, ROLE_PARENT, ROLE_LOGISTICS, ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN}:
        raise ValueError("repair close denied")
    _ensure_repair_visible(identity, ticket)
    ticket["status"] = "closed"
    _append_timeline(ticket, "repair.closed", str(identity.get("user_id", "system")), {})
    _save_json(_entity_path(project_root, "repair_tickets", ticket_id), ticket)
    if audit_writer:
        audit_writer("campus.repair.closed", identity, {"ticket_id": ticket_id})
    return ticket


def run_repair_timeouts(project_root: Path, *, audit_writer: AuditWriter | None = None) -> list[dict[str, Any]]:
    now = _now()
    timed_out: list[dict[str, Any]] = []
    for ticket in _list_entity(project_root, "repair_tickets"):
        if ticket.get("status") in {"closed", "completed", "timeout"}:
            continue
        deadline = datetime.fromisoformat(str(ticket["deadline_at"]))
        if deadline >= now:
            continue
        ticket["status"] = "timeout"
        _append_timeline(ticket, "repair.timeout", "system", {})
        _save_json(_entity_path(project_root, "repair_tickets", str(ticket["ticket_id"])), ticket)
        _create_reminder(project_root, {
            "biz_type": "repair_ticket",
            "biz_id": ticket["ticket_id"],
            "receiver_type": "role",
            "receiver_id": ROLE_LOGISTICS,
            "channel": "wecom_app",
            "template_id": "repair_timeout",
            "payload_json": {"ticket_id": ticket["ticket_id"]},
            "school_id": ticket.get("school_id", "school_demo"),
        })
        timed_out.append(ticket)
        if audit_writer:
            audit_writer("campus.repair.timeout", {"user_id": "system", "role": "system", "school_id": ticket.get("school_id", "school_demo")}, {"ticket_id": ticket["ticket_id"]})
    return timed_out


def generate_daily_report(project_root: Path, identity: dict[str, Any], report_date: str) -> dict[str, Any]:
    if identity.get("role") not in ADMINISTRATIVE_ROLES:
        raise ValueError("daily report access denied")
    leaves = [item for item in _list_entity(project_root, "leave_requests") if str(item.get("created_at", "")).startswith(report_date)]
    meals = [item for item in _list_entity(project_root, "meal_orders") if str(item.get("meal_date", "")) == report_date]
    repairs = [
        item for item in _list_entity(project_root, "repair_tickets")
        if str(item.get("created_at", "")).startswith(report_date) or str(item.get("updated_at", "")).startswith(report_date)
    ]
    summary = {
        "date": report_date,
        "school_id": _visible_school(identity),
        "leave": {
            "total": len(leaves),
            "approved": sum(1 for item in leaves if item.get("status") == "approved"),
            "rejected": sum(1 for item in leaves if item.get("status") == "rejected"),
            "pending": sum(1 for item in leaves if item.get("status") == "pending"),
        },
        "meal": {
            "total": len(meals),
            "cancelled": sum(1 for item in meals if item.get("status") == "cancelled"),
            "locked": sum(1 for item in meals if item.get("status") == "locked"),
        },
        "repair": {
            "total": len(repairs),
            "completed": sum(1 for item in repairs if item.get("status") == "completed"),
            "closed": sum(1 for item in repairs if item.get("status") == "closed"),
            "timeout": sum(1 for item in repairs if item.get("status") == "timeout"),
        },
    }
    summary["narrative"] = (
        f"{report_date} 请假 {summary['leave']['total']} 单，"
        f"订餐/退餐 {summary['meal']['total']} 单，"
        f"报修 {summary['repair']['total']} 单。"
    )
    report_id = f"daily_{report_date.replace('-', '')}"
    report = {
        "report_id": report_id,
        "report_date": report_date,
        "summary": summary,
        "generated_by": identity.get("user_id", "system"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _save_json(_entity_path(project_root, "daily_reports", report_id), report)
    return report
