from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

CST = timezone(timedelta(hours=8))

from app.db.repositories import reminder_tasks as tasks_repo


def create_vendor_reminders(
    school_id: str,
    meal_lock_id: str,
    confirmation_id: str,
    confirm_url: str,
    meal_date: str,
    meal_type: str,
    net_total: int,
    vendor_name: str = "",
) -> list[dict]:
    base_payload = {
        "meal_lock_id": meal_lock_id,
        "vendor_confirmation_id": confirmation_id,
        "confirm_url": confirm_url,
        "meal_date": meal_date,
        "meal_type": meal_type,
        "net_total": net_total,
        "vendor_name": vendor_name,
    }

    now = datetime.now(CST)

    tasks = [
        {
            "reminder_id": f"RT-{uuid4().hex[:12]}",
            "school_id": school_id,
            "biz_type": "vendor_confirmation",
            "biz_id": confirmation_id,
            "receiver_type": "vendor",
            "receiver_id": vendor_name or "vendor",
            "channel": "group_bot",
            "template_id": "vendor_confirmation_send",
            "payload_json": base_payload,
            "scheduled_at": now,
            "idempotency_key": f"vendor_cfm_send_{confirmation_id}",
        },
    ]

    results = []
    for task in tasks:
        result = tasks_repo.create_reminder_task(task)
        if result:
            results.append(result)

    return results
