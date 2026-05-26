from __future__ import annotations

from typing import Any
from recommendation_model import ClassRecommendation, RecommendationInput
from class_rules import recommend as rules_recommend


def generate_recommendation(profile: dict, allowed_evidence: list[dict], campus: str | None = None, role: str = "parent", consultation_stage: str = "NEEDS_ASSESSMENT") -> ClassRecommendation:
    inp = RecommendationInput(profile=profile, allowed_evidence=allowed_evidence, campus=campus, role=role, consultation_stage=consultation_stage)
    rec = rules_recommend(inp)
    
    # Add missing profile fields to missing_info
    known_keys = set(profile.keys())
    needed = ["current_score", "subject_type", "target_school_level", "weak_subjects", "self_discipline_level", "budget_range", "preferred_campus", "boarding_preference"]
    for key in needed:
        if key not in known_keys or not profile.get(key):
            if key not in rec.missing_info:
                rec.missing_info.append(key)
    
    return rec
