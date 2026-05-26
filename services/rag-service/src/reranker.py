from __future__ import annotations

from typing import Any


def rerank(scored: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

