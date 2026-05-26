from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from app.db.connection import get_conn
from app.services.redaction import redact


def heartbeat(
    worker_name: str,
    *,
    school_id: str | None = None,
    status: str = "running",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO worker_heartbeats (worker_name, school_id, status, metadata_json)
            VALUES (%(worker_name)s, %(school_id)s, %(status)s, %(metadata_json)s)
            ON CONFLICT (worker_name) DO UPDATE SET
                school_id = EXCLUDED.school_id,
                status = EXCLUDED.status,
                metadata_json = EXCLUDED.metadata_json,
                last_heartbeat_at = now()
            RETURNING *
            """,
            {
                "worker_name": worker_name,
                "school_id": school_id,
                "status": status,
                "metadata_json": Jsonb(redact(metadata or {})),
            },
        ).fetchone()


def get_heartbeat(worker_name: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM worker_heartbeats WHERE worker_name = %(worker_name)s",
            {"worker_name": worker_name},
        ).fetchone()


def list_heartbeats() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM worker_heartbeats ORDER BY worker_name",
        ).fetchall()
