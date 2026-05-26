from __future__ import annotations

import json
from typing import Any

from app.db.connection import get_conn


def create_reminder_task(data: dict[str, Any]) -> dict[str, Any] | None:
    if "payload_json" in data and not isinstance(data["payload_json"], str):
        data["payload_json"] = json.dumps(data["payload_json"], ensure_ascii=False)
    sql = """
    INSERT INTO reminder_tasks (
        reminder_id, school_id, biz_type, biz_id, receiver_type, receiver_id,
        channel, template_id, payload_json, scheduled_at, idempotency_key
    )
    VALUES (
        %(reminder_id)s, %(school_id)s, %(biz_type)s, %(biz_id)s,
        %(receiver_type)s, %(receiver_id)s,
        %(channel)s, %(template_id)s, %(payload_json)s::jsonb, %(scheduled_at)s,
        %(idempotency_key)s
    )
    ON CONFLICT (school_id, idempotency_key) WHERE idempotency_key IS NOT NULL
    DO NOTHING
    RETURNING *;
    """
    with get_conn() as conn:
        return conn.execute(sql, data).fetchone()


def claim_due_tasks(worker_id: str, limit: int = 20, school_id: str | None = None) -> list[dict[str, Any]]:
    sql = """
    WITH due AS (
        SELECT reminder_id
        FROM reminder_tasks rt
        WHERE rt.status = 'pending'
          AND rt.scheduled_at <= now()
          AND (CAST(%(school_id)s AS TEXT) IS NULL OR rt.school_id = CAST(%(school_id)s AS TEXT))
          AND NOT EXISTS (
              SELECT 1 FROM mealbot_runtime_controls control
              WHERE control.school_id = rt.school_id
                AND control.reminder_worker_enabled = false
          )
        ORDER BY rt.scheduled_at ASC
        LIMIT %(limit)s
        FOR UPDATE SKIP LOCKED
    )
    UPDATE reminder_tasks rt
    SET
        status = 'processing',
        locked_at = now(),
        locked_by = %(worker_id)s
    FROM due
    WHERE rt.reminder_id = due.reminder_id
    RETURNING rt.*;
    """
    with get_conn() as conn:
        return conn.execute(sql, {"worker_id": worker_id, "limit": limit, "school_id": school_id}).fetchall()


def mark_sent(reminder_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE reminder_tasks
            SET status = 'sent', sent_at = now(), locked_at = NULL, locked_by = NULL
            WHERE reminder_id = %(reminder_id)s
            RETURNING *""",
            {"reminder_id": reminder_id},
        ).fetchone()


def mark_skipped(reminder_id: str, reason: str = "") -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE reminder_tasks
            SET status = 'skipped', last_error = %(reason)s,
                locked_at = NULL, locked_by = NULL
            WHERE reminder_id = %(reminder_id)s
            RETURNING *""",
            {"reminder_id": reminder_id, "reason": reason},
        ).fetchone()


def mark_failed_or_retry(reminder_id: str, error: str, max_retries: int = 3) -> dict[str, Any] | None:
    sql = """
    UPDATE reminder_tasks
    SET
        retry_count = retry_count + 1,
        last_error = %(error)s,
        status = CASE
            WHEN retry_count + 1 >= %(max_retries)s THEN 'failed'
            ELSE 'pending'
        END,
        scheduled_at = CASE
            WHEN retry_count + 1 >= %(max_retries)s THEN scheduled_at
            ELSE now() + (CASE retry_count + 1
                WHEN 1 THEN '1 minute'::interval
                WHEN 2 THEN '5 minutes'::interval
                ELSE '15 minutes'::interval
            END)
        END,
        locked_at = NULL,
        locked_by = NULL
    WHERE reminder_id = %(reminder_id)s
    RETURNING *;
    """
    with get_conn() as conn:
        return conn.execute(sql, {"reminder_id": reminder_id, "error": error, "max_retries": max_retries}).fetchone()


def get_pending_tasks() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM reminder_tasks
            WHERE status = 'pending'
              AND scheduled_at <= now()
            ORDER BY scheduled_at
            LIMIT 50""",
        ).fetchall()
