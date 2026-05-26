from __future__ import annotations

import json
from datetime import date, datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

CST = timezone(timedelta(hours=8))

from app.db.repositories import attachments as attachments_repo
from app.db.repositories import delivery_confirmations as delivery_repo
from app.db.repositories import meal_locks as locks_repo
from app.db.repositories import meal_orders as orders_repo
from app.db.repositories import students as students_repo
from app.db.repositories import vendor_confirmations as vendor_repo
from app.modules.meal.vendor import generate_raw_token, token_to_hash, expires_at


class MealLockedError(ValueError):
    def __init__(self, meal_date: date, meal_type: str):
        self.code = "MEAL_LOCKED"
        self.meal_date = meal_date
        self.meal_type = meal_type
        super().__init__(f"meal locked: {meal_date} {meal_type}")


def _check_meal_locked(school_id: str, meal_date: date, meal_type: str) -> None:
    existing = locks_repo.get_lock(school_id, meal_date, meal_type)
    if existing is not None:
        raise MealLockedError(meal_date, meal_type)


def submit_meal_order(
    *,
    school_id: str,
    student_id: str,
    class_id: str,
    meal_date: date,
    meal_type: str,
    action: str,
    reason: str | None = None,
    dietary_note: str | None = None,
    submitted_by_wecom_userid: str | None = None,
    attachment: dict | None = None,
    admin_override: bool = False,
) -> dict[str, Any]:
    student = students_repo.get_student(student_id)
    if not student:
        raise ValueError("STUDENT_NOT_FOUND")
    if student["school_id"] != school_id:
        raise ValueError("STUDENT_NOT_IN_SCHOOL")

    valid_actions = {"order", "cancel", "add"}
    if action not in valid_actions:
        raise ValueError(f"INVALID_ACTION: must be one of {valid_actions}")

    valid_meal_types = {"lunch", "dinner", "extra"}
    if meal_type not in valid_meal_types:
        raise ValueError(f"INVALID_MEAL_TYPE: must be one of {valid_meal_types}")

    if not admin_override:
        _check_meal_locked(school_id, meal_date, meal_type)

    order_id = f"MO-{uuid4().hex[:12]}"

    order = orders_repo.create_or_update_order({
        "order_id": order_id,
        "school_id": school_id,
        "student_id": student_id,
        "class_id": class_id,
        "meal_date": meal_date,
        "meal_type": meal_type,
        "action": action,
        "reason": reason,
        "dietary_note": dietary_note,
        "submitted_by_wecom_userid": submitted_by_wecom_userid,
        "status": "submitted",
    })

    if attachment:
        attachments_repo.create_attachment({
            "attachment_id": f"ATT-{uuid4().hex[:12]}",
            "school_id": school_id,
            "source": attachment.get("source", "h5_upload"),
            "biz_type": "meal_order",
            "biz_id": order_id,
            "file_path": attachment["file_path"],
            "original_name": attachment.get("original_name"),
            "content_type": attachment.get("content_type"),
            "size_bytes": attachment.get("size_bytes"),
            "sha256": attachment.get("sha256"),
            "created_by_wecom_userid": submitted_by_wecom_userid,
        })

    return order


def list_student_orders(student_id: str, meal_date: date | None = None) -> list[dict[str, Any]]:
    return orders_repo.list_orders_for_student(student_id, meal_date)


def cancel_meal_order(order_id: str) -> dict[str, Any] | None:
    order = orders_repo.get_order(order_id)
    if not order:
        raise ValueError("ORDER_NOT_FOUND")
    if order["status"] in ("locked", "summarized", "closed"):
        raise ValueError("ORDER_CANNOT_BE_CANCELLED")
    return orders_repo.cancel_order(order_id)


# ── Lock & Summary ──────────────────────────────────────────────

def _build_summary_snapshot(school_id: str, meal_date: date, meal_type: str) -> dict[str, Any]:
    orders = orders_repo.list_orders_for_school(school_id, meal_date, meal_type)

    total_order = 0
    total_cancel = 0
    total_add = 0
    special_items: list[dict[str, Any]] = []
    by_class: dict[str, dict[str, Any]] = {}

    for o in orders:
        cid = o.get("class_id", "unknown")
        if cid not in by_class:
            by_class[cid] = {"class_name": o.get("class_id", ""), "order": 0, "cancel": 0, "add": 0, "special": 0}
        if o["action"] == "order":
            total_order += 1
            by_class[cid]["order"] += 1
        elif o["action"] == "cancel":
            total_cancel += 1
            by_class[cid]["cancel"] += 1
        elif o["action"] == "add":
            total_add += 1
            by_class[cid]["add"] += 1

        if o.get("dietary_note") and str(o["dietary_note"]).strip():
            by_class[cid]["special"] += 1
            special_items.append({
                "student_id": o["student_id"],
                "dietary_note": o["dietary_note"],
                "class_id": cid,
            })

    net_total = total_order + total_add - total_cancel

    for cid in by_class:
        by_class[cid]["net_total"] = by_class[cid]["order"] + by_class[cid]["add"] - by_class[cid]["cancel"]

    return {
        "school_id": school_id,
        "meal_date": meal_date.isoformat(),
        "meal_type": meal_type,
        "total_order": total_order,
        "total_cancel": total_cancel,
        "total_add": total_add,
        "net_total": max(0, net_total),
        "special_count": len(special_items),
        "by_class": list(by_class.values()),
        "special_items": special_items,
    }


def lock_meal(
    school_id: str,
    meal_date: date,
    meal_type: str,
    locked_by: str = "system",
) -> dict[str, Any]:
    existing = locks_repo.get_lock(school_id, meal_date, meal_type)
    if existing:
        return {"lock": existing, "locked_count": 0, "message": "already_locked"}

    snapshot = _build_summary_snapshot(school_id, meal_date, meal_type)
    if snapshot["total_order"] == 0 and snapshot["total_cancel"] == 0 and snapshot["total_add"] == 0:
        raise ValueError("NO_ORDERS_TO_LOCK")

    locked = orders_repo.lock_orders_for_summary(school_id, meal_date, meal_type)

    lock = locks_repo.create_or_update_lock({
        "lock_id": f"ML-{uuid4().hex[:12]}",
        "school_id": school_id,
        "meal_date": meal_date,
        "meal_type": meal_type,
        "status": "locked",
        "locked_by": locked_by,
        "summary_snapshot": snapshot,
    })

    return {
        "lock": lock,
        "locked_count": len(locked),
        "snapshot": snapshot,
    }


def generate_vendor_confirmation(
    lock_id: str,
    school_id: str,
    vendor_name: str = "",
    vendor_contact: str = "",
    expires_in_minutes: int = 180,
) -> dict[str, Any]:
    lock = _get_lock_by_id(lock_id)
    if not lock:
        raise ValueError("LOCK_NOT_FOUND")
    if str(lock.get("school_id", "")) != school_id:
        raise ValueError("LOCK_NOT_IN_SCHOOL")

    raw_token, token_hash = generate_raw_token()
    exp = expires_at(expires_in_minutes)

    confirmation = vendor_repo.create_vendor_confirmation({
        "confirmation_id": f"VC-{uuid4().hex[:12]}",
        "school_id": school_id,
        "meal_lock_id": lock_id,
        "vendor_name": vendor_name,
        "vendor_contact": vendor_contact,
        "token_hash": token_hash,
        "expires_at": exp,
        "status": "pending",
    })

    locks_repo.update_lock_status(lock_id, "sent_to_vendor")

    from app.modules.meal.vendor_reminders import create_vendor_reminders
    snapshot = lock.get("summary_snapshot", {})
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except (json.JSONDecodeError, TypeError):
            snapshot = {}
    create_vendor_reminders(
        school_id=school_id,
        meal_lock_id=lock_id,
        confirmation_id=confirmation["confirmation_id"],
        confirm_url=f"/vendor/confirm?t={raw_token}",
        meal_date=str(lock.get("meal_date", "")),
        meal_type=lock.get("meal_type", ""),
        net_total=snapshot.get("net_total", 0),
        vendor_name=vendor_name,
    )

    return {
        "confirmation": confirmation,
        "confirm_url": f"/vendor/confirm?t={raw_token}",
    }


def get_logistics_summary(school_id: str, meal_date: date, meal_type: str | None = None) -> dict[str, Any]:
    locks = locks_repo.get_locks_for_date(school_id, meal_date)
    result: dict[str, Any] = {
        "school_id": school_id,
        "meal_date": meal_date.isoformat(),
        "locks": [],
    }

    for lock in locks:
        if meal_type and lock["meal_type"] != meal_type:
            continue

        pending_confirmations = vendor_repo.get_pending_for_lock(lock["lock_id"])

        snapshot = lock.get("summary_snapshot", {})
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except (json.JSONDecodeError, TypeError):
                snapshot = {}

        result["locks"].append({
            "lock_id": lock["lock_id"],
            "meal_type": lock["meal_type"],
            "status": lock["status"],
            "locked_at": lock.get("locked_at"),
            "locked_by": lock.get("locked_by"),
            "snapshot": snapshot,
            "pending_confirmations": pending_confirmations,
        })

    return result


def confirm_vendor(token: str, action: str = "confirmed", confirmed_by: str = "", abnormal_note: str = "") -> dict[str, Any]:
    token_hash = token_to_hash(token)
    confirmation = vendor_repo.get_by_token_hash(token_hash)
    if not confirmation:
        raise ValueError("INVALID_VENDOR_TOKEN")

    if confirmation["status"] == "confirmed":
        raise ValueError("ALREADY_CONFIRMED")
    if confirmation["status"] == "expired":
        raise ValueError("VENDOR_CONFIRMATION_EXPIRED")
    if confirmation["expires_at"] and confirmation["expires_at"] < datetime.now(CST):
        vendor_repo.mark_expired(confirmation["confirmation_id"])
        raise ValueError("VENDOR_CONFIRMATION_EXPIRED")

    if action == "abnormal":
        confirmed = vendor_repo.mark_abnormal(confirmation["confirmation_id"], confirmed_by, abnormal_note)
    else:
        confirmed = vendor_repo.confirm(confirmation["confirmation_id"], confirmed_by)

    if confirmed:
        locks_repo.update_lock_status(confirmation["meal_lock_id"], "closed")

    return {"ok": True, "confirmation": confirmed, "action": action}


def get_vendor_confirmation_info(token: str) -> dict[str, Any]:
    token_hash = token_to_hash(token)
    confirmation = vendor_repo.get_by_token_hash(token_hash)
    if not confirmation:
        return {"ok": False, "error": {"code": "INVALID_TOKEN", "message": "无效的确认链接"}}

    expired = False
    if confirmation["status"] == "expired":
        expired = True
    elif confirmation["expires_at"] and confirmation["expires_at"] < datetime.now(CST):
        vendor_repo.mark_expired(confirmation["confirmation_id"])
        expired = True

    lock = None
    lock_row = _get_lock_by_id(confirmation["meal_lock_id"])
    if lock_row:
        snapshot = lock_row.get("summary_snapshot", {})
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except (json.JSONDecodeError, TypeError):
                snapshot = {}
        lock = {
            "lock_id": lock_row["lock_id"],
            "meal_type": lock_row["meal_type"],
            "meal_date": str(lock_row.get("meal_date", "")),
            "status": lock_row["status"],
            "snapshot": snapshot,
        }

    return {
        "ok": True,
        "confirmation_id": confirmation["confirmation_id"],
        "vendor_name": confirmation.get("vendor_name", ""),
        "status": "expired" if expired else confirmation["status"],
        "expires_at": confirmation.get("expires_at"),
        "lock": lock,
    }


def _get_lock_by_id(lock_id: str) -> dict[str, Any] | None:
    from app.db.connection import get_conn
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM meal_locks WHERE lock_id = %(lock_id)s",
            {"lock_id": lock_id},
        ).fetchone()
