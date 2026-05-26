from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Any

from app.db.connection import get_conn

CST = timezone(timedelta(hours=8))


def create_delivery(data: dict[str, Any]) -> dict[str, Any] | None:
    sql = """
    INSERT INTO delivery_confirmations (
        delivery_id, school_id, meal_date, meal_type, vendor_id,
        total_count, special_count, status, token_hash
    )
    VALUES (
        %(delivery_id)s, %(school_id)s, %(meal_date)s, %(meal_type)s,
        %(vendor_id)s, %(total_count)s, %(special_count)s,
        %(status)s, %(token_hash)s
    )
    ON CONFLICT DO NOTHING
    RETURNING *;
    """
    data.setdefault("status", "pending")
    data.setdefault("special_count", 0)
    with get_conn() as conn:
        return conn.execute(sql, data).fetchone()


def get_delivery(delivery_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM delivery_confirmations WHERE delivery_id = %(delivery_id)s",
            {"delivery_id": delivery_id},
        ).fetchone()


def get_delivery_by_token_hash(token_hash: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM delivery_confirmations WHERE token_hash = %(token_hash)s",
            {"token_hash": token_hash},
        ).fetchone()


def confirm_delivery(delivery_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE delivery_confirmations
            SET status = 'confirmed', confirmed_at = now()
            WHERE delivery_id = %(delivery_id)s
              AND status NOT IN ('confirmed', 'closed')
            RETURNING *""",
            {"delivery_id": delivery_id},
        ).fetchone()


def get_pending_deliveries(school_id: str, meal_date: date | None = None) -> list[dict[str, Any]]:
    sql = """SELECT * FROM delivery_confirmations
    WHERE school_id = %(school_id)s
      AND status IN ('pending', 'locked')"""
    params: dict[str, Any] = {"school_id": school_id}
    if meal_date:
        sql += " AND meal_date = %(meal_date)s"
        params["meal_date"] = meal_date
    sql += " ORDER BY meal_date, meal_type"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()
