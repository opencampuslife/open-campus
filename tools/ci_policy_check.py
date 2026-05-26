from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    errors: list[str] = []
    errors.extend(check_production_json(args.root))
    errors.extend(check_database_urls())
    errors.extend(check_provider_isolation(args.root))
    errors.extend(check_sql_policy(args.root))
    errors.extend(check_db_retriever_context(args.root))

    if errors:
        for error in errors:
            print(f"CI POLICY FAIL: {error}")
        return 1
    print("ci policy checks: OK")
    return 0


def check_production_json(root: Path) -> list[str]:
    env = os.environ.get("GAOKAO_ENV")
    source = os.environ.get("RAG_SOURCE")
    errors: list[str] = []
    if env == "production" and source == "json":
        errors.append("GAOKAO_ENV=production must not use RAG_SOURCE=json")

    policy_text = (root / "configs" / "retrieval_policy.yaml").read_text(encoding="utf-8")
    required = [
        "production_source: postgres",
        "allow_json_in_production: false",
    ]
    for needle in required:
        if needle not in policy_text:
            errors.append(f"retrieval_policy.yaml missing {needle}")
    return errors


def check_database_urls() -> list[str]:
    errors: list[str] = []
    for name in ("DATABASE_URL_PUBLIC", "DATABASE_URL_STAFF"):
        value = os.environ.get(name)
        if not value:
            continue
        username = urlparse(value).username
        if username in {"postgres", "db_admin"}:
            errors.append(f"{name} must not use admin database user {username}")
    return errors


def check_provider_isolation(root: Path) -> list[str]:
    errors: list[str] = []
    orchestrator_src = root / "services" / "agent-orchestrator" / "src"
    forbidden = ("provider_deepseek", "chat_completion", "DEEPSEEK_API_KEY")
    for path in orchestrator_src.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                errors.append(f"orchestrator must not import/use provider detail {token}: {path}")
    return errors


def check_sql_policy(root: Path) -> list[str]:
    migrations = root / "services" / "db-policy-service" / "migrations"
    sql = "\n".join(path.read_text(encoding="utf-8") for path in sorted(migrations.glob("*.sql")))
    errors: list[str] = []
    if "SECURITY DEFINER" in sql:
        errors.append("migrations must not use SECURITY DEFINER")
    if re.search(r"SET\s+app\.", sql, flags=re.IGNORECASE):
        errors.append("migrations must not use global SET app.*")
    required = [
        "FORCE ROW LEVEL SECURITY",
        "SECURITY INVOKER",
        "REVOKE ALL ON knowledge_chunks FROM gaokao_api_public",
    ]
    for needle in required:
        if needle not in sql:
            errors.append(f"migrations missing {needle}")
    return errors


def check_db_retriever_context(root: Path) -> list[str]:
    text = (root / "services" / "rag-service" / "src" / "db_retriever.py").read_text(encoding="utf-8")
    errors: list[str] = []
    required = [
        "BEGIN;",
        "SET LOCAL app.user_id",
        "SET LOCAL app.role",
        "SET LOCAL app.campus",
        "SET LOCAL app.auth_level",
        "search_accessible_chunks",
        "ROLLBACK;",
    ]
    for needle in required:
        if needle not in text:
            errors.append(f"db_retriever.py missing {needle}")
    if "SET app.role" in text:
        errors.append("db_retriever.py must not use connection-level SET app.role")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())

