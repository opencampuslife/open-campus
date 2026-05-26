from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PERMISSION_SRC = Path(__file__).resolve().parents[2] / "permission-service" / "src"
sys.path.append(str(PERMISSION_SRC))

from access_checker import can_access  # noqa: E402


def filter_allowed(chunks: list[dict[str, Any]], scope: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed: list[dict[str, Any]] = []
    denied: list[dict[str, Any]] = []
    for chunk in chunks:
        ok, reason = can_access(chunk, scope)
        if ok:
            allowed.append(chunk)
        else:
            denied.append({"chunk_id": chunk["chunk_id"], "doc_id": chunk["doc_id"], "reason": reason})
    return allowed, denied

