from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

KNOWLEDGE_SRC = Path(__file__).resolve().parents[2] / "knowledge-service" / "src"
sys.path.append(str(KNOWLEDGE_SRC))

from simple_yaml import load_file  # noqa: E402

from db_retriever import search_db
from retriever import search as search_json


def search_knowledge(
    query: str,
    scope: dict[str, Any],
    project_root: Path,
    *,
    entrypoint: str = "public_chat",
    force_source: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    source = force_source or resolve_retrieval_source(project_root)
    if source == "postgres":
        return search_db(query, scope, project_root, entrypoint=entrypoint, limit=limit)
    return search_json(query, scope, project_root, limit=limit)


def resolve_retrieval_source(project_root: Path) -> str:
    configured = os.environ.get("RAG_SOURCE")
    if configured:
        return configured

    policy = load_file(project_root / "configs" / "retrieval_policy.yaml").get("retrieval_source", {})
    env = os.environ.get("GAOKAO_ENV", "development")
    if env == "production":
        return str(policy.get("production_source", "postgres"))
    return str(policy.get("dev_fallback_source", "json"))
