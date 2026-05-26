from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.db.connection import get_conn
from app.services.redaction import redact


def write_operation_log(
    *,
    school_id: str,
    actor_user_id: str,
    biz_type: str,
    biz_id: str,
    action: str,
    actor_type: str = "user",
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO operation_logs (
                log_id, school_id, actor_user_id, biz_type, biz_id,
                action, actor_type, request_id, ip_address, user_agent,
                before_json, after_json, metadata_json
            ) VALUES (
                %(log_id)s, %(school_id)s, %(actor_user_id)s, %(biz_type)s, %(biz_id)s,
                %(action)s, %(actor_type)s, %(request_id)s, %(ip_address)s, %(user_agent)s,
                %(before_json)s, %(after_json)s, %(metadata_json)s
            )
            RETURNING *
            """,
            {
                "log_id": f"LOG-{uuid4().hex[:12]}",
                "school_id": school_id,
                "actor_user_id": actor_user_id,
                "biz_type": biz_type,
                "biz_id": biz_id,
                "action": action,
                "actor_type": actor_type,
                "request_id": request_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "before_json": Jsonb(redact(before or {})),
                "after_json": Jsonb(redact(after or {})),
                "metadata_json": Jsonb(redact(metadata or {})),
            },
        ).fetchone()
