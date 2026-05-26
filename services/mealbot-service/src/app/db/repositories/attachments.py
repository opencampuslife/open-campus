from __future__ import annotations

from typing import Any

from app.db.connection import get_conn


def create_attachment(data: dict[str, Any]) -> dict[str, Any]:
    sql = """
    INSERT INTO attachments (
        attachment_id, school_id, source, biz_type, biz_id,
        file_path, original_name, content_type, size_bytes, sha256,
        created_by_wecom_userid
    )
    VALUES (
        %(attachment_id)s, %(school_id)s, %(source)s, %(biz_type)s, %(biz_id)s,
        %(file_path)s, %(original_name)s, %(content_type)s, %(size_bytes)s, %(sha256)s,
        %(created_by_wecom_userid)s
    )
    RETURNING *;
    """
    with get_conn() as conn:
        return conn.execute(sql, data).fetchone()


def get_attachment(attachment_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM attachments WHERE attachment_id = %(attachment_id)s",
            {"attachment_id": attachment_id},
        ).fetchone()


def get_attachments_for_biz(biz_type: str, biz_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM attachments WHERE biz_type = %(biz_type)s AND biz_id = %(biz_id)s ORDER BY created_at",
            {"biz_type": biz_type, "biz_id": biz_id},
        ).fetchall()


def link_attachment_to_meal_order(attachment_id: str, order_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE attachments
            SET biz_type = 'meal_order', biz_id = %(order_id)s
            WHERE attachment_id = %(attachment_id)s
              AND (biz_type IS NULL OR biz_type = 'inbound_message'
                   OR (biz_type = 'meal_order' AND biz_id = %(order_id)s))
            RETURNING *""",
            {"attachment_id": attachment_id, "order_id": order_id},
        ).fetchone()


def link_attachment_to_biz(attachment_id: str, biz_type: str, biz_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE attachments SET biz_type = %(biz_type)s, biz_id = %(biz_id)s
            WHERE attachment_id = %(attachment_id)s
              AND (biz_type IS NULL OR (biz_type = %(biz_type)s AND biz_id = %(biz_id)s))
            RETURNING *
            """,
            {"attachment_id": attachment_id, "biz_type": biz_type, "biz_id": biz_id},
        ).fetchone()
