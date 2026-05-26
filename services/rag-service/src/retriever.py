from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from citation_builder import build_citations
from metadata_filter import filter_allowed
from query_rewriter import expand_query
from reranker import rerank
from source_policy import enforce_json_index_allowed

PERMISSION_SRC = Path(__file__).resolve().parents[2] / "permission-service" / "src"
sys.path.append(str(PERMISSION_SRC))

from scope_builder import build_scope  # noqa: E402


def search(query: str, scope: dict[str, Any], project_root: Path, limit: int = 5) -> dict[str, Any]:
    enforce_json_index_allowed(project_root)
    index_path = project_root / "data" / "indexes" / "knowledge_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))

    expanded_query = expand_query(query, intent="faq")
    search_query = f"{query} {expanded_query}"

    pre_allowed, pre_denied = filter_allowed(index["chunks"], scope)
    scored = []
    seen_docs: set[str] = set()
    for chunk in pre_allowed:
        score = _score_weighted(search_query, chunk)
        if score > 0:
            item = dict(chunk)
            item["score"] = score
            if chunk["doc_id"] not in seen_docs:
                seen_docs.add(chunk["doc_id"])
            scored.append(item)

    ranked = rerank(scored, limit=limit)
    post_allowed, post_denied = filter_allowed(ranked, scope)
    return {
        "query": query,
        "allowed_chunks": post_allowed,
        "citations": build_citations(post_allowed),
        "denied_pre_filter": pre_denied,
        "denied_post_filter": post_denied,
        "confidence": min(1.0, sum(c["score"] for c in post_allowed) / 6.0),
    }


WEIGHT_TITLE: float = 4.0
WEIGHT_TAGS: float = 3.0
WEIGHT_HEADING: float = 3.0
WEIGHT_CONTENT: float = 1.0


def _score_weighted(query: str, chunk: dict[str, Any]) -> float:
    q_terms = _terms(query)

    title_terms = _terms(chunk.get("title", ""))
    tag_terms = _terms(" ".join(chunk.get("business_tags", [])))
    content_text = chunk.get("content", "")

    heading = _extract_heading(content_text)
    heading_terms = _terms(heading)
    content_terms = _terms(content_text)

    if not q_terms:
        return 0.0

    title_score = _overlap_score(q_terms, title_terms) * WEIGHT_TITLE
    tag_score = _overlap_score(q_terms, tag_terms) * WEIGHT_TAGS
    heading_score = _overlap_score(q_terms, heading_terms) * WEIGHT_HEADING
    content_score = _overlap_score(q_terms, content_terms) * WEIGHT_CONTENT

    total = title_score + tag_score + heading_score + content_score
    return math.log1p(total)


HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)$", re.MULTILINE)


def _extract_heading(content: str) -> str:
    matches = HEADING_RE.findall(content)
    return " ".join(m.replace("#", "").strip() for m in matches)


def _overlap_score(q_terms: list[str], target_terms: list[str]) -> float:
    if not q_terms or not target_terms:
        return 0.0
    counter = Counter(target_terms)
    overlap = sum(counter[t] for t in q_terms)
    return overlap / max(len(q_terms), 1)


def _terms(text: str) -> list[str]:
    latin = re.findall(r"[A-Za-z0-9_]+", text.lower())
    cjk_terms: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        cjk_terms.append(run)
        for width in (2, 3, 4):
            cjk_terms.extend(run[i : i + width] for i in range(0, max(0, len(run) - width + 1)))
    return latin + cjk_terms


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--query", required=True)
    parser.add_argument("--identity", required=True, help="JSON identity")
    args = parser.parse_args()
    scope = build_scope(json.loads(args.identity), args.root)
    print(json.dumps(search(args.query, scope, args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
