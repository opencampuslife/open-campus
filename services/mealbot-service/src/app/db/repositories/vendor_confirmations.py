from __future__ import annotations

from typing import Any

from app.db.connection import get_conn


def create_vendor_confirmation(data: dict[str, Any]) -> dict[str, Any]:
    sql = """
    INSERT INTO vendor_confirmations (
        confirmation_id, school_id, meal_lock_id,
        vendor_name, vendor_contact,
        token_hash, expires_at, status
    )
    VALUES (
        %(confirmation_id)s, %(school_id)s, %(meal_lock_id)s,
        %(vendor_name)s, %(vendor_contact)s,
        %(token_hash)s, %(expires_at)s, %(status)s
    )
    RETURNING *;
    """
    data.setdefault("confirmation_id", "")
    data.setdefault("school_id", "")
    data.setdefault("meal_lock_id", "")
    data.setdefault("vendor_name", None)
    data.setdefault("vendor_contact", None)
    data.setdefault("token_hash", "")
    data.setdefault("expires_at", None)
    data.setdefault("status", "pending")
    with get_conn() as conn:
        return conn.execute(sql, data).fetchone()


def get_by_token_hash(token_hash: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM vendor_confirmations WHERE token_hash = %(token_hash)s",
            {"token_hash": token_hash},
        ).fetchone()


def confirm(confirmation_id: str, confirmed_by: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE vendor_confirmations
            SET status = 'confirmed', confirmed_at = now(), confirmed_by = %(confirmed_by)s
            WHERE confirmation_id = %(confirmation_id)s
              AND status = 'pending'
            RETURNING *""",
            {"confirmation_id": confirmation_id, "confirmed_by": confirmed_by},
        ).fetchone()


def mark_abnormal(confirmation_id: str, confirmed_by: str, note: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE vendor_confirmations
            SET status = 'abnormal', abnormal_note = %(note)s,
                confirmed_at = now(), confirmed_by = %(confirmed_by)s
            WHERE confirmation_id = %(confirmation_id)s
              AND status = 'pending'
            RETURNING *""",
            {"confirmation_id": confirmation_id, "confirmed_by": confirmed_by, "note": note},
        ).fetchone()


def mark_expired(confirmation_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE vendor_confirmations
            SET status = 'expired'
            WHERE confirmation_id = %(confirmation_id)s AND status = 'pending'
              AND expires_at < now()
            RETURNING *""",
            {"confirmation_id": confirmation_id},
        ).fetchone()


def get_pending_for_lock(meal_lock_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM vendor_confirmations
            WHERE meal_lock_id = %(meal_lock_id)s AND status = 'pending'
            ORDER BY created_at""",
            {"meal_lock_id": meal_lock_id},
        ).fetchall()
