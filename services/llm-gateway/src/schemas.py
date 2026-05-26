from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    doc_id: str
    title: str
    content: str
    visibility: str
    data_level: str
    allowed_roles: list[str]
    source_uri: str

    @classmethod
    def from_chunk(cls, chunk: dict[str, Any]) -> "EvidenceChunk":
        return cls(
            chunk_id=str(chunk["chunk_id"]),
            doc_id=str(chunk["doc_id"]),
            title=str(chunk["title"]),
            content=str(chunk["content"]),
            visibility=str(chunk["visibility"]),
            data_level=str(chunk["data_level"]),
            allowed_roles=list(chunk.get("allowed_roles", [])),
            source_uri=str(chunk.get("source_uri", "")),
        )

    def to_prompt_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LLMRequest:
    user_role: str
    intent: str
    user_query: str
    allowed_evidence: list[EvidenceChunk]
    answer_policy: dict[str, Any] = field(default_factory=dict)
    output_format: str = "plain_text_with_sources"
    risk_level: str = "low"
    session_id: str = ""
    campus: str = "all"

    def to_policy_dict(self) -> dict[str, Any]:
        return {
            "task": "admissions_answer",
            "message": self.user_query,
            "intent": self.intent,
            "scope": {
                "role": self.user_role,
                "campus": self.campus,
            },
            "risk_level": self.risk_level,
            "session_id": self.session_id,
            "answer_policy": self.answer_policy,
            "output_format": self.output_format,
            "evidence": [chunk.to_prompt_dict() for chunk in self.allowed_evidence],
        }

