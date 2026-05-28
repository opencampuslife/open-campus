"""ExecutorAgent — dry-run execution planner (P3-A skeleton).

P3-A: generates execution steps from TaskGraph. No real GitHub write.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from ..models import AgentRole, TaskRun
from .base import AgentResult, BaseAgent
from ..execution import ExecutionPlanner, ExecutionPlan
from ..tool_registry import ToolRegistry


class ExecutorAgent(BaseAgent):
    """Converts an approved TaskRun + TaskGraph into an ExecutionPlan.

    P3-A: purely model-driven. No LLM. No real write operations.
    """

    role: ClassVar[AgentRole] = AgentRole.EXECUTOR

    def __init__(self) -> None:
        super().__init__()
        self._planner = ExecutionPlanner()
        self._registry = ToolRegistry()

    def run(self, task: TaskRun) -> AgentResult:
        if task.task_graph is None:
            return AgentResult(success=False, error="no task_graph: plan() must be called first")

        try:
            plan = self._planner.plan(task, task.task_graph)
        except Exception as exc:
            return AgentResult(success=False, error=str(exc))

        return AgentResult(
            success=True,
            data={
                "execution_plan": plan.to_dict(),
                "step_count": plan.step_count,
                "tools_registered": self._registry.list_tools(),
                "dry_run": plan.dry_run,
            },
        )

    @staticmethod
    def plan(task: TaskRun) -> ExecutionPlan:
        """Convenience static method to generate an ExecutionPlan."""
        planner = ExecutionPlanner()
        return planner.plan(task, task.task_graph)


def _call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"