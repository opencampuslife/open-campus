from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.db.repositories import reminder_tasks as tasks_repo

CST = timezone(timedelta(hours=8))

TASK_TYPE_MAP = {
    "order": "meal_order_submitted",
    "cancel": "meal_cancel_submitted",
    "add": "meal_add_submitted",
}


def create_meal_notification(
    *,
    school_id: str,
    order_id: str,
    student_id: str,
    meal_date: str,
    meal_type: str,
    action: str,
    receiver_type: str = "logistics",
    receiver_id: str = "default",
) -> dict | None:
    task_type = TASK_TYPE_MAP.get(action, "meal_order_submitted")

    scheduled_at = datetime.now(CST)

    payload = {
        "order_id": order_id,
        "student_id": student_id,
        "meal_date": str(meal_date),
        "meal_type": meal_type,
        "action": action,
        "receiver_type": receiver_type,
    }

    try:
        return tasks_repo.create_reminder_task({
            "reminder_id": f"RT-{uuid4().hex[:12]}",
            "school_id": school_id,
            "biz_type": "meal_order",
            "biz_id": order_id,
            "receiver_type": receiver_type,
            "receiver_id": receiver_id,
            "channel": "wecom_app_message",
            "template_id": task_type,
            "payload_json": payload,
            "scheduled_at": scheduled_at,
            "idempotency_key": f"meal_{order_id}_{task_type}",
        })
    except Exception as exc:
        import logging
        logging.getLogger("mealbot").warning("reminder task creation failed: %s", exc)
        return None
