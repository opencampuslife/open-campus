from __future__ import annotations

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
bt_path = AGENT_ROOT / "bt"
sys.path.insert(0, str(bt_path))

from base import ActionNode, AgentContext, BTStatus  # noqa: E402


class GenerateConsultationAnswer(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from policies.admissions_answer_policy import build_admissions_answer

        rec = getattr(ctx, "recommendation_result", None)
        if rec and hasattr(rec, "__dict__"):
            rec = rec.__dict__
        elif rec and hasattr(rec, "_asdict"):
            rec = rec._asdict()

        answer = build_admissions_answer(
            message=ctx.message,
            intent=ctx.intent,
            profile=ctx.profile,
            profile_completeness=ctx.profile_completeness,
            consultation_stage=getattr(ctx, "consultation_stage", "NEEDS_ASSESSMENT"),
            recommendation=rec,
            allowed_evidence=ctx.allowed_chunks,
            identity_type=ctx.profile.get("identity_type", "parent"),
        )
        ctx.answer_draft = answer
        ctx.audit_events.append(
            {
                "type": "consultation_answer",
                "stage": ctx.consultation_stage,
                "recommendation_used": bool(rec and rec.get("recommended_class_type")),
            }
        )
        return BTStatus.SUCCESS
