from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

LLM_GATEWAY_SRC = Path(__file__).resolve().parents[2] / "llm-gateway" / "src"
sys.path.append(str(LLM_GATEWAY_SRC))

from gateway import generate_admissions_answer  # noqa: E402
from schemas import EvidenceChunk, LLMRequest  # noqa: E402


def generate_answer(
    message: str,
    retrieval: dict[str, Any],
    intent: str,
    scope: dict[str, Any],
    project_root: Path | None = None,
) -> str:
    if project_root is not None:
        llm_request = LLMRequest(
            user_role=scope["role"],
            intent=intent,
            user_query=message,
            allowed_evidence=[EvidenceChunk.from_chunk(chunk) for chunk in retrieval["allowed_chunks"]],
            answer_policy={"must_cite_sources": True, "forbid_promises": True},
            risk_level="low",
            campus=scope.get("campus", "all"),
        )
        llm_answer = generate_admissions_answer(
            project_root=project_root,
            request=llm_request,
        )
        if llm_answer:
            return llm_answer

    chunks = retrieval["allowed_chunks"]
    if not chunks:
        return "我暂时没有检索到当前身份可访问的已审核资料。建议补充校区、班型或咨询目标，或转人工顾问确认。"

    evidence_text = "\n".join(_clean_chunk(c["content"]) for c in chunks[:3])
    source_titles = "、".join(dict.fromkeys(c["title"] for c in chunks[:3]))

    if scope["role"] == "sales" and any(c["visibility"] == "internal" for c in chunks):
        return f"内部参考：\n{evidence_text}\n\n来源：{source_titles}\n注意：以上内容仅供顾问内部使用，不应原样发送给家长或学生。"

    if intent == "pricing_consulting":
        return (
            f"关于费用，可以按公开口径说明：{evidence_text}\n\n"
            "具体费用会受校区、班型、课程周期和学生学情影响，建议预约顾问结合学生情况确认。"
            f"\n\n来源：{source_titles}"
        )

    if intent == "class_recommendation":
        return (
            f"从你描述的情况看，可以优先了解全日制、管理较强的复读方案。{evidence_text}\n\n"
            "最终适合的班型还要结合入学测评、薄弱科目和目标分数判断，不能承诺固定提分结果。"
            f"\n\n来源：{source_titles}"
        )

    return f"{evidence_text}\n\n来源：{source_titles}"


def _clean_chunk(content: str) -> str:
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped:
            lines.append(stripped)
    return " ".join(lines)
