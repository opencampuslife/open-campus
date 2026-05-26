from __future__ import annotations

import json
import logging
from typing import Any

from app.db.repositories import reminder_tasks as tasks_repo
from app.db.repositories import operation_logs as logs_repo
from app.db.repositories import vendor_confirmations as vendor_repo
from app.services.message_adapters import get_adapter

log = logging.getLogger("reminder_service")


def process_due_reminders(worker_id: str = "default") -> dict[str, int]:
    tasks = tasks_repo.claim_due_tasks(worker_id, limit=20)
    counts = {"processed": len(tasks), "sent": 0, "skipped": 0, "failed": 0}

    for task in tasks:
        try:
            should_send, skip_reason = _check_business_guard(task)
            if not should_send:
                tasks_repo.mark_skipped(task["reminder_id"], skip_reason)
                _write_task_result(task, "reminder_task.skipped", {"reason": skip_reason})
                counts["skipped"] += 1
                continue

            adapter = get_adapter(task["channel"])
            result = adapter.send(task)

            if result.get("ok"):
                tasks_repo.mark_sent(task["reminder_id"])
                _write_task_result(task, "reminder_task.sent")
                counts["sent"] += 1
            else:
                tasks_repo.mark_failed_or_retry(
                    task["reminder_id"],
                    result.get("error", "unknown error"),
                )
                _write_task_result(task, "reminder_task.failed", {"error": "delivery_failed"})
                counts["failed"] += 1

        except Exception as exc:
            tasks_repo.mark_failed_or_retry(task["reminder_id"], str(exc))
            _write_task_result(task, "reminder_task.failed", {"error": "processing_failed"})
            counts["failed"] += 1
            log.warning("reminder processing failed: %s", task.get("reminder_id"), exc_info=True)

    return counts


def _write_task_result(task: dict[str, Any], action: str, after: dict[str, Any] | None = None) -> None:
    logs_repo.write_operation_log(
        school_id=str(task["school_id"]),
        actor_user_id="reminder_worker",
        biz_type=str(task["biz_type"]),
        biz_id=str(task["biz_id"]),
        action=action,
        after={"reminder_id": task["reminder_id"], **(after or {})},
    )


def _check_business_guard(task: dict[str, Any]) -> tuple[bool, str]:
    if task["biz_type"] == "vendor_confirmation":
        return _guard_vendor_confirmation(task)

    return True, ""


def _guard_vendor_confirmation(task: dict[str, Any]) -> tuple[bool, str]:
    payload = task.get("payload_json", {})
    if isinstance(payload, str):
        payload = json.loads(payload)

    vc_id = payload.get("vendor_confirmation_id")
    if not vc_id:
        return True, ""

    confirmation = vendor_repo.get_by_token_hash("")
    if not confirmation:
        pass

    from app.db.connection import get_conn
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status, expires_at FROM vendor_confirmations WHERE confirmation_id = %(cid)s",
            {"cid": vc_id},
        ).fetchone()

    if not row:
        return False, "vendor_confirmation_not_found"

    if row["status"] == "confirmed":
        return False, "already_confirmed"

    if row["status"] == "abnormal":
        return False, "already_abnormal"

    if row["status"] == "expired":
        return False, "already_expired"

    from datetime import datetime, timezone, timedelta
    CST = timezone(timedelta(hours=8))
    if row["expires_at"] and row["expires_at"] < datetime.now(CST):
        vendor_repo.mark_expired(vc_id)
        return False, "expired_before_send"

    return True, ""
