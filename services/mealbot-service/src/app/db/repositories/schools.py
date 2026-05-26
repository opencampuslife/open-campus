from __future__ import annotations

from typing import Any

from app.db.connection import get_conn


def get_school(school_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM schools WHERE school_id = %(school_id)s",
            {"school_id": school_id},
        ).fetchone()


def get_school_by_corp_id(corp_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM schools WHERE wecom_corp_id = %(corp_id)s",
            {"corp_id": corp_id},
        ).fetchone()
