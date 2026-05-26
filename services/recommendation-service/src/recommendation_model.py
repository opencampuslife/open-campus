from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class RecommendationInput:
    profile: dict[str, Any]
    allowed_evidence: list[dict[str, Any]]
    campus: str | None = None
    role: str = "parent"
    consultation_stage: str = "NEEDS_ASSESSMENT"

@dataclass
class ClassRecommendation:
    recommended_class_type: str | None = None
    confidence: str = "low"  # high / medium / low
    reasons: list[str] = field(default_factory=list)
    not_suitable_if: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    next_questions: list[str] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
