"""ResearcherAgent — gathers codebase context (P2-A skeleton).

P2-A: No real RAG or repo reading. Returns mock context.
"""

from __future__ import annotations

from typing import ClassVar

from ..models import AgentRole, TaskRun
from .base import AgentResult, BaseAgent


class ResearcherAgent(BaseAgent):
    role: ClassVar[AgentRole] = AgentRole.RESEARCHER

    def run(self, task: TaskRun) -> AgentResult:
        return AgentResult(
            success=True,
            data={
                "context": f"Skeleton context for: {task.goal[:80]}",
                "files_found": 0,
                "note": "P2-A skeleton — no real RAG or repo reading",
            },
        )
