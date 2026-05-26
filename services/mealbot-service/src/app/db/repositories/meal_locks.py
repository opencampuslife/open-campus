from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.db.connection import get_conn


def create_or_update_lock(data: dict[str, Any]) -> dict[str, Any]:
    if "summary_snapshot" in data and not isinstance(data["summary_snapshot"], str):
        data["summary_snapshot"] = json.dumps(data["summary_snapshot"], ensure_ascii=False)
    sql = """
    INSERT INTO meal_locks (
        lock_id, school_id, meal_date, meal_type, status, locked_by, summary_snapshot
    )
    VALUES (
        %(lock_id)s, %(school_id)s, %(meal_date)s, %(meal_type)s,
        %(status)s, %(locked_by)s, %(summary_snapshot)s::jsonb
    )
    ON CONFLICT (school_id, meal_date, meal_type)
    DO UPDATE SET
        status = %(status)s,
        summary_snapshot = EXCLUDED.summary_snapshot,
        updated_at = now()
    RETURNING *;
    """
    data.setdefault("status", "locked")
    with get_conn() as conn:
        return conn.execute(sql, data).fetchone()


def get_lock(school_id: str, meal_date: date, meal_type: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM meal_locks
            WHERE school_id = %(school_id)s AND meal_date = %(meal_date)s AND meal_type = %(meal_type)s""",
            {"school_id": school_id, "meal_date": meal_date, "meal_type": meal_type},
        ).fetchone()


def update_lock_status(lock_id: str, status: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "UPDATE meal_locks SET status = %(status)s WHERE lock_id = %(lock_id)s RETURNING *",
            {"lock_id": lock_id, "status": status},
        ).fetchone()


def get_locks_for_date(school_id: str, meal_date: date) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM meal_locks
            WHERE school_id = %(school_id)s AND meal_date = %(meal_date)s
            ORDER BY meal_type""",
            {"school_id": school_id, "meal_date": meal_date},
        ).fetchall()
