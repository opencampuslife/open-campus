from __future__ import annotations

import os
import sys
from pathlib import Path

KNOWLEDGE_SRC = Path(__file__).resolve().parents[2] / "knowledge-service" / "src"
sys.path.append(str(KNOWLEDGE_SRC))

from simple_yaml import load_file  # noqa: E402


def enforce_json_index_allowed(project_root: Path) -> None:
    env = os.environ.get("GAOKAO_ENV", "development")
    source = os.environ.get("RAG_SOURCE", "json")
    policy = load_file(project_root / "configs" / "retrieval_policy.yaml").get("retrieval_source", {})
    allow_json_in_production = bool(policy.get("allow_json_in_production", False))
    if env == "production" and source == "json" and not allow_json_in_production:
        raise RuntimeError("JSON knowledge index is disabled in production; use RAG_SOURCE=postgres")


def require_postgres_in_production() -> None:
    env = os.environ.get("GAOKAO_ENV", "development")
    source = os.environ.get("RAG_SOURCE", "json")
    if env == "production" and source != "postgres":
        raise RuntimeError("Production RAG must use postgres hard-boundary retrieval")

