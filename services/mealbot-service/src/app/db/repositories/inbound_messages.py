from __future__ import annotations

from typing import Any

from app.db.connection import get_conn


def create_inbound_message_idempotent(data: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    sql = """
    INSERT INTO inbound_messages (
        msg_id, school_id, from_wecom_userid, msg_type, agent_id,
        media_id, pic_url, raw_xml, status
    )
    VALUES (
        %(msg_id)s, %(school_id)s, %(from_wecom_userid)s, %(msg_type)s, %(agent_id)s,
        %(media_id)s, %(pic_url)s, %(raw_xml)s, %(status)s
    )
    ON CONFLICT (msg_id) DO NOTHING
    RETURNING *;
    """
    data.setdefault("status", "received")
    with get_conn() as conn:
        row = conn.execute(sql, data).fetchone()
        if row:
            return row, True
        return get_inbound_message(data["msg_id"]), False


def create_inbound_message(data: dict[str, Any]) -> dict[str, Any] | None:
    row, _ = create_inbound_message_idempotent(data)
    return row


def update_inbound_message_status(msg_id: str, status: str, last_error: str | None = None) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE inbound_messages
            SET status = %(status)s, last_error = %(last_error)s
            WHERE msg_id = %(msg_id)s
            RETURNING *""",
            {"msg_id": msg_id, "status": status, "last_error": last_error},
        ).fetchone()


def get_inbound_message(msg_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM inbound_messages WHERE msg_id = %(msg_id)s",
            {"msg_id": msg_id},
        ).fetchone()


def claim_pending_downloads(limit: int = 20, school_id: str | None = None) -> list[dict[str, Any]]:
    sql = """
    WITH pending AS (
        SELECT msg_id
        FROM inbound_messages inbound
        WHERE inbound.status = 'download_pending'
          AND (CAST(%(school_id)s AS TEXT) IS NULL OR inbound.school_id = CAST(%(school_id)s AS TEXT))
          AND NOT EXISTS (
              SELECT 1 FROM mealbot_runtime_controls control
              WHERE control.school_id = inbound.school_id
                AND control.wecom_media_worker_enabled = false
          )
        ORDER BY inbound.created_at
        LIMIT %(limit)s
        FOR UPDATE SKIP LOCKED
    )
    UPDATE inbound_messages inbound
    SET status = 'processing'
    FROM pending
    WHERE inbound.msg_id = pending.msg_id
    RETURNING inbound.*;
    """
    with get_conn() as conn:
        return conn.execute(sql, {"limit": limit, "school_id": school_id}).fetchall()


def mark_downloaded(msg_id: str, attachment_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE inbound_messages
            SET status = 'downloaded', attachment_id = %(attachment_id)s, last_error = NULL
            WHERE msg_id = %(msg_id)s
            RETURNING *""",
            {"msg_id": msg_id, "attachment_id": attachment_id},
        ).fetchone()
