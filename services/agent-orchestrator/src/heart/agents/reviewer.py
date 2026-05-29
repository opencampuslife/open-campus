"""ReviewerAgent — reviews plans and code (P2-A skeleton).

P2-A: No real review logic. Returns placeholder verdict.
"""

from __future__ import annotations

from typing import ClassVar

from ..models import AgentRole, TaskRun
from .base import AgentResult, BaseAgent


class ReviewerAgent(BaseAgent):
    role: ClassVar[AgentRole] = AgentRole.REVIEWER

    def run(self, task: TaskRun) -> AgentResult:
        return AgentResult(
            success=True,
            data={
                "verdict": "pass",
                "checks": [
                    {"category": "architecture", "passed": True},
                    {"category": "security", "passed": True},
                    {"category": "compliance", "passed": True},
                ],
                "note": "P2-A skeleton — no real review logic",
            },
        )
