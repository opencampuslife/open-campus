from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from citation_builder import build_citations
from query_rewriter import expand_query
from source_policy import require_postgres_in_production


ENTRYPOINT_DATABASE_ENV = {
    "public_chat": "DATABASE_URL_PUBLIC",
    "student_portal": "DATABASE_URL_PUBLIC",
    "parent_portal": "DATABASE_URL_PUBLIC",
    "sales_console": "DATABASE_URL_STAFF",
    "teacher_console": "DATABASE_URL_STAFF",
    "operator_console": "DATABASE_URL_STAFF",
    "admin_console": "DATABASE_URL_ADMIN_APP",
}

PSQL = Path(__file__).resolve().parents[3] / "services" / "db-policy-service" / "scripts" / "psql.sh"


def search_db(
    query: str,
    identity: dict[str, Any],
    project_root: Path,
    *,
    entrypoint: str = "public_chat",
    limit: int = 5,
    database_url: str | None = None,
) -> dict[str, Any]:
    require_postgres_in_production()
    database_url = database_url or get_database_url_for_entrypoint(entrypoint)
    sql = _build_search_sql(expand_query(query), identity, limit)
    chunks = _run_json_query(database_url, sql)
    return {
        "query": query,
        "allowed_chunks": chunks,
        "citations": build_citations(chunks),
        "denied_pre_filter": [],
        "denied_post_filter": [],
        "confidence": min(1.0, len(chunks) / max(1, limit)),
        "source": "postgres",
    }


def get_database_url_for_entrypoint(entrypoint: str) -> str:
    if entrypoint not in ENTRYPOINT_DATABASE_ENV:
        raise ValueError(f"Unknown entrypoint: {entrypoint}")
    env_name = ENTRYPOINT_DATABASE_ENV[entrypoint]
    url = os.environ.get(env_name)
    if not url:
        raise RuntimeError(f"{env_name} is not set")
    parsed = urlparse(url)
    if env_name != "DATABASE_URL_ADMIN_APP" and parsed.username in {"postgres", "db_admin"}:
        raise RuntimeError(f"{env_name} must not use the admin postgres connection")
    return url


def _build_search_sql(query: str, identity: dict[str, Any], limit: int) -> str:
    role = _sql_literal(str(identity["role"]))
    campus = _sql_literal(str(identity.get("campus", "all")))
    user_id = _sql_literal(str(identity.get("user_id", "")))
    auth_level = _sql_literal(str(identity.get("auth_level", "")))
    query_text = _sql_literal(query)
    limit_int = max(1, min(int(limit), 20))
    return f"""
BEGIN;
SET LOCAL app.user_id = {user_id};
SET LOCAL app.role = {role};
SET LOCAL app.campus = {campus};
SET LOCAL app.auth_level = {auth_level};
SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)
FROM (
    SELECT
        chunk_id,
        chunk_id AS id,
        split_part(chunk_id, '::', 1) AS doc_id,
        title,
        content,
        source_uri,
        source_page,
        visibility,
        data_level,
        data_level_int,
        business_tags,
        ARRAY[]::text[] AS allowed_roles,
        ARRAY[]::text[] AS campus_scope
    FROM search_accessible_chunks({query_text}, {limit_int})
) t;
ROLLBACK;
"""


def _run_json_query(database_url: str, sql: str) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            [str(PSQL), database_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"postgres retrieval failed: {details or 'unable to query database'}") from exc
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            return json.loads(stripped)
    return []


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
