from __future__ import annotations

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
bt_path = AGENT_ROOT / "bt"
sys.path.insert(0, str(bt_path))

from base import ActionNode, AgentContext, BTStatus  # noqa: E402


class DetermineConsultationStage(ActionNode):
    def tick(self, ctx: AgentContext) -> BTStatus:
        from consultation.stage import determine_stage, ConsultationStage

        session_has_handoff = getattr(ctx, "handoff_triggered", False)
        stage = determine_stage(
            profile=ctx.profile,
            profile_completeness=ctx.profile_completeness,
            message=ctx.message,
            intent=ctx.intent,
            fsm_state=ctx.fsm_state if hasattr(ctx, "fsm_state") else "CONSULTING",
            session_has_handoff=session_has_handoff,
        )
        ctx.consultation_stage = stage.value
        ctx.audit_events.append({"type": "consultation_stage", "stage": ctx.consultation_stage})
        return BTStatus.SUCCESS
