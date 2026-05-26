from __future__ import annotations

from typing import Any


def build_citations(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    citations: list[dict[str, str]] = []
    for chunk in chunks:
        key = chunk["doc_id"]
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "source_uri": chunk["source_uri"],
            }
        )
    return citations

