from __future__ import annotations

import re
from typing import Any


ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\uFEFF]")
WHITESPACE_COLLAPSE_RE = re.compile(r"\s+")


INJECTION_PATTERNS = [
    "忽略以上",
    "忽略之前",
    "ignore previous",
    "ignore above",
    "system prompt",
    "developer message",
    "越权",
    "绕过",
]


def _normalize(text: str) -> str:
    text = ZERO_WIDTH_RE.sub("", text)
    text = WHITESPACE_COLLAPSE_RE.sub(" ", text)
    return text.lower().strip()


def validate_llm_request(request: dict[str, Any]) -> tuple[bool, list[str]]:
    violations: list[str] = []
    message = str(request.get("message", ""))
    evidence = str(request.get("evidence", ""))
    joined = f"{message}\n{evidence}"
    normalized = _normalize(joined)
    for pattern in INJECTION_PATTERNS:
        if pattern.lower() in normalized:
            violations.append(f"prompt_injection_pattern:{pattern}")

    scope = request.get("scope", {})
    required_evidence_fields = {
        "chunk_id",
        "doc_id",
        "title",
        "content",
        "visibility",
        "data_level",
        "allowed_roles",
        "source_uri",
    }
    for chunk in request.get("evidence", []):
        missing = required_evidence_fields - set(chunk)
        if missing:
            violations.append(f"evidence_missing_fields:{','.join(sorted(missing))}")

    if scope.get("role") in {"visitor", "student", "parent"}:
        for chunk in request.get("evidence", []):
            if chunk.get("visibility") == "internal" or chunk.get("data_level") in {"L3", "L4"}:
                violations.append("external_request_contains_internal_evidence")
                break
    return not violations, violations
