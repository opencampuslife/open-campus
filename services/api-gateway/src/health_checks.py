from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

MEALBOT_SRC = Path(__file__).resolve().parents[2] / "mealbot-service" / "src"
if str(MEALBOT_SRC) not in sys.path:
    sys.path.insert(0, str(MEALBOT_SRC))

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def public_health(project_root: Path) -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.2.0",
        "timestamp": _now_iso(),
    }


def healthz(project_root: Path) -> dict[str, Any]:
    del project_root
    return {"ok": True}


def readyz(project_root: Path) -> dict[str, Any]:
    from app.config import load_settings

    settings = load_settings()
    checks: dict[str, str] = {}
    errors = settings.validation_errors()
    checks["config"] = "ok" if not errors else "invalid"
    try:
        import psycopg

        with psycopg.connect(settings.database_url) as conn:
            conn.execute("SELECT 1").fetchone()
            migration_ready = conn.execute(
                """SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables WHERE table_name = 'worker_heartbeats'
                ) AND EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'inbound_messages' AND column_name = 'attachment_id'
                )"""
            ).fetchone()[0]
        checks["postgres"] = "ok"
        checks["migrations"] = "current" if migration_ready else "missing"
        if not migration_ready:
            errors.append("required release-hardening migrations are missing")
    except Exception:
        checks["postgres"] = "unavailable"
        errors.append("database unavailable")

    upload_dir = Path(settings.upload_dir)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        marker = upload_dir / ".readyz"
        marker.write_text("ok", encoding="utf-8")
        marker.unlink()
        checks["uploads"] = "writable"
    except Exception:
        checks["uploads"] = "unavailable"
        errors.append("upload directory not writable")

    return {"ok": not errors, "checks": checks, "errors": errors, "config": settings.safe_summary()}


def worker_status(project_root: Path) -> dict[str, Any]:
    del project_root
    from app.db.connection import get_conn
    from app.db.repositories.worker_heartbeats import list_heartbeats

    workers = {row["worker_name"]: {
        "last_heartbeat_at": row["last_heartbeat_at"].isoformat() if row.get("last_heartbeat_at") else None,
        "status": row["status"],
        "metadata": row.get("metadata_json", {}),
    } for row in list_heartbeats()}
    with get_conn() as conn:
        reminder = conn.execute(
            "SELECT count(*) FILTER (WHERE status = 'pending') pending, count(*) FILTER (WHERE status = 'failed') failed FROM reminder_tasks"
        ).fetchone()
        media = conn.execute(
            "SELECT count(*) FILTER (WHERE status = 'download_pending') pending, count(*) FILTER (WHERE status = 'failed') failed FROM inbound_messages"
        ).fetchone()
    workers.setdefault("reminder_worker", {}).update({
        "pending_tasks": reminder["pending"], "failed_tasks": reminder["failed"],
    })
    workers.setdefault("wecom_media_worker", {}).update({
        "download_pending": media["pending"], "failed": media["failed"],
    })
    return {"ok": True, "workers": workers}


def db_health(project_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown",
        "checks": {},
        "errors": [],
    }

    db_url = os.environ.get("DATABASE_URL_ADMIN") or os.environ.get("DATABASE_URL_PUBLIC")
    if not db_url:
        result["status"] = "unavailable"
        result["errors"].append("no DATABASE_URL configured")
        return result

    try:
        import psycopg2

        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT 1")
        result["checks"]["connection"] = "ok"

        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        if cur.fetchone():
            result["checks"]["pgvector"] = "installed"
        else:
            result["checks"]["pgvector"] = "missing"
            result["errors"].append("pgvector extension not installed")

        cur.execute("""
            SELECT 1 FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public' AND p.proname = 'search_accessible_chunks'
        """)
        if cur.fetchone():
            result["checks"]["search_accessible_chunks"] = "exists"
        else:
            result["checks"]["search_accessible_chunks"] = "not found"
            result["errors"].append("search_accessible_chunks function not found")

        cur.execute("""
            SELECT relname, relforcerowsecurity
            FROM pg_class JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
            WHERE nspname = 'public' AND relname = 'knowledge_documents' AND relforcerowsecurity
        """)
        if cur.fetchone():
            result["checks"]["rls_on_knowledge_documents"] = "enabled"
        else:
            result["checks"]["rls_on_knowledge_documents"] = "not enabled"
            result["errors"].append("RLS not enabled on knowledge_documents")

        cur.close()
        conn.close()

        result["status"] = "ok" if not result["errors"] else "degraded"
    except ImportError:
        result["status"] = "unavailable"
        result["errors"].append("psycopg2 not installed")
    except Exception as exc:
        result["status"] = "error"
        result["errors"].append("db error: {}".format(str(exc)))

    return result


def rag_health(project_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown",
        "checks": {},
        "errors": [],
    }

    rag_source = os.environ.get("RAG_SOURCE", "json")

    if rag_source == "postgres":
        db_result = db_health(project_root)
        result["checks"]["postgres"] = db_result["status"]
        if db_result["status"] != "ok":
            result["status"] = "degraded"
            result["errors"].extend(db_result.get("errors", []))
    else:
        index_path = project_root / "data" / "indexes" / "index.json"
        if index_path.exists():
            result["checks"]["json_index"] = "exists"
        else:
            result["checks"]["json_index"] = "missing"
            result["errors"].append("JSON index not found, run 'make index'")

    published_dir = project_root / "data" / "published"
    if published_dir.exists() and list(published_dir.iterdir()):
        result["checks"]["published_docs"] = "available"
    else:
        result["checks"]["published_docs"] = "empty"
        if rag_source == "json":
            result["errors"].append("no published documents found")

    if not result["errors"]:
        result["status"] = "ok"
    elif result["status"] == "unknown":
        result["status"] = "degraded"

    return result


def llm_health(project_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown",
        "checks": {},
        "errors": [],
    }

    config_path = project_root / "configs" / "llm_config.json"
    if config_path.exists():
        result["checks"]["config_file"] = "exists"
    else:
        result["checks"]["config_file"] = "missing"
        result["errors"].append("llm_config.json not found")

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        result["checks"]["api_key"] = "configured"
    else:
        result["checks"]["api_key"] = "not set"
        result["errors"].append("DEEPSEEK_API_KEY not configured")

    enable_llm = os.environ.get("DEEPSEEK_ENABLE_LLM", "0")
    result["checks"]["llm_enabled"] = enable_llm == "1"

    if not result["errors"]:
        result["status"] = "ok"
    else:
        result["status"] = "degraded"

    return result


def security_health(project_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown",
        "checks": {},
        "errors": [],
    }

    csrf_secret = os.environ.get("CSRF_TOKEN_SECRET", "")
    if csrf_secret and len(csrf_secret) >= 32:
        result["checks"]["csrf_secret"] = "configured"
    else:
        result["checks"]["csrf_secret"] = "weak_or_missing"
        result["errors"].append("CSRF_TOKEN_SECRET not properly configured")

    remote_ingestion = os.environ.get("ENABLE_REMOTE_URL_INGESTION", "0")
    result["checks"]["remote_url_ingestion"] = "disabled" if remote_ingestion != "1" else "enabled"
    if remote_ingestion == "1":
        result["errors"].append("ENABLE_REMOTE_URL_INGESTION is enabled in production")


    app_env = os.environ.get("GAOKAO_ENV", "development")
    result["checks"]["app_env"] = app_env
    result["checks"]["identity_override"] = "disabled" if app_env == "production" else "enabled"
    if app_env != "production":
        result["errors"].append("GAOKAO_ENV is not production; identity override possible")

    try:
        from rate_limiter import DEFAULT_ADMIN_LIMIT, DEFAULT_CHAT_LIMIT
        result["checks"]["rate_limit_chat"] = "{} req/min".format(DEFAULT_CHAT_LIMIT)
        result["checks"]["rate_limit_admin"] = "{} req/min".format(DEFAULT_ADMIN_LIMIT)
    except ImportError:
        result["checks"]["rate_limiter"] = "not available"
        result["errors"].append("rate_limiter module not importable")

    if not result["errors"]:
        result["status"] = "ok"
    else:
        result["status"] = "degraded"

    return result


def filesystem_health(project_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "unknown",
        "checks": {},
        "errors": [],
    }

    check_dirs = {
        "knowledge_vault": ("knowledge_vault", True),
        "data_crm": ("data/crm", True),
        "data_staging": ("data/staging", True),
        "data_ingestion": ("data/ingestion", True),
        "data_graph_runs": ("data/graph-runs", True),
        "data_audit_logs": ("data/audit_logs", True),
        "data_published": ("data/published", True),
        "configs": ("configs", False),
    }

    for name, (rel_path, need_write) in check_dirs.items():
        fs_path = project_root / rel_path
        if fs_path.exists():
            if need_write:
                try:
                    test_file = fs_path / ".health_check_test"
                    test_file.write_text(_now_iso())
                    test_file.unlink()
                    result["checks"][name] = "read-write"
                except Exception:
                    result["checks"][name] = "exists (not writable)"
                    result["errors"].append("{} not writable".format(rel_path))
            else:
                result["checks"][name] = "exists" if list(fs_path.iterdir()) else "exists (empty)"
        else:
            result["checks"][name] = "missing"
            result["errors"].append("{} directory missing".format(rel_path))

    if not result["errors"]:
        result["status"] = "ok"
    else:
        result["status"] = "degraded"

    return result


def full_health_check(project_root: Path) -> dict[str, Any]:
    checks = {
        "db": db_health(project_root),
        "rag": rag_health(project_root),
        "llm": llm_health(project_root),
        "security": security_health(project_root),
        "filesystem": filesystem_health(project_root),
    }

    statuses = [c["status"] for c in checks.values()]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif "error" in statuses:
        overall = "error"
    else:
        overall = "degraded"

    return {
        "status": overall,
        "version": "0.2.0",
        "request_id": uuid.uuid4().hex,
        "timestamp": _now_iso(),
        "checks": checks,
    }
