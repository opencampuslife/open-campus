from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
bt_path = AGENT_ROOT / "bt"
SERVICES_ROOT = Path(__file__).resolve().parents[4]
RECOMMENDATION_SRC = SERVICES_ROOT / "services" / "recommendation-service" / "src"
sys.path.extend([str(bt_path), str(RECOMMENDATION_SRC)])

from base import ActionNode, AgentContext, BTStatus  # noqa: E402


class ClassRecommendationRouting(ActionNode):
    """Route consultation stages without allowing recommendation to bypass RLS evidence."""

    POLICY_STAGES = {"CLASS_RECOMMENDING", "PLAN_EXPLAINING", "OBJECTION_HANDLING", "READY_FOR_HANDOFF"}

    def tick(self, ctx: AgentContext) -> BTStatus:
        stage = ctx.consultation_stage
        if stage not in self.POLICY_STAGES:
            return BTStatus.FAILURE

        if stage in {"OBJECTION_HANDLING", "READY_FOR_HANDOFF"}:
            ctx.audit_events.append({"type": "recommendation_not_required", "stage": stage})
            return BTStatus.SUCCESS

        if not ctx.allowed_chunks:
            ctx.audit_events.append({"type": "recommendation_skipped", "stage": stage, "reason": "no_allowed_evidence"})
            return BTStatus.FAILURE

        from recommendation_engine import generate_recommendation

        recommendation = generate_recommendation(
            profile=ctx.profile,
            allowed_evidence=ctx.allowed_chunks,
            campus=ctx.campus,
            role=ctx.role,
            consultation_stage=stage,
        )
        ctx.recommendation_result = asdict(recommendation)
        ctx.audit_events.append(
            {
                "type": "class_recommendation",
                "stage": stage,
                "recommended_class_type": recommendation.recommended_class_type,
                "confidence": recommendation.confidence,
                "evidence_chunk_ids": recommendation.evidence_ids,
            }
        )
        return BTStatus.SUCCESS
