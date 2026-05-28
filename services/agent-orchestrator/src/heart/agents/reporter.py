"""ReporterAgent — generates delivery reports (P2-A skeleton).

P2-A: No real report generation. Returns placeholder summary.
"""

from __future__ import annotations

from typing import ClassVar

from ..models import AgentRole, TaskRun
from .base import AgentResult, BaseAgent


class ReporterAgent(BaseAgent):
    role: ClassVar[AgentRole] = AgentRole.REPORTER

    def run(self, task: TaskRun) -> AgentResult:
        return AgentResult(
            success=True,
            data={
                "summary": f"Heart Mode task report for: {task.goal[:80]}",
                "node_count": task.task_graph.node_count if task.task_graph else 0,
                "status": task.status.value,
                "note": "P2-A skeleton — no real report generation",
            },
        )
