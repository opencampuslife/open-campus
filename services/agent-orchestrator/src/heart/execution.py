"""Execution planning models for Heart Mode.

P3-A scope: dry-run execution planner. No real GitHub write. No CI run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── ExecutionStep ─────────────────────────────────────────────────────────

@dataclass
class ExecutionStep:
    """Single step in an ExecutionPlan."""
    id: str                              # "step_<n>"
    title: str                           # human-readable description
    tool_name: str                       # registered tool name
    input: dict[str, Any] = field(default_factory=dict)
    expected_output: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False       # step-level approval gate
    risk_level: str = "low"              # "low" | "medium" | "high" | "critical"
    status: str = "pending"             # "pending" | "dry_run_done" | "executed" | "failed" | "skipped"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "tool_name": self.tool_name,
            "input": self.input,
            "expected_output": self.expected_output,
            "requires_approval": self.requires_approval,
            "risk_level": self.risk_level,
            "status": self.status,
        }


# ── ExecutionPlan ─────────────────────────────────────────────────────────

@dataclass
class ExecutionPlan:
    """Plan of execution for an approved task."""
    task_id: str
    status: str = "planned"             # "planned" | "in_progress" | "completed" | "failed"
    steps: list[ExecutionStep] = field(default_factory=list)
    dry_run: bool = True                 # P3-A always True; reserved for P3-B
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str | None = None

    def update_status(self, new: str) -> None:
        self.status = new
        self.updated_at = _now_iso()

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "step_count": self.step_count,
            "dry_run": self.dry_run,
            "created_at": self.created_at,
            "updated_at": self.updated_at or "",
            "steps": [s.to_dict() for s in self.steps],
        }


# ── ExecutionPlanner ──────────────────────────────────────────────────────

from .models import AgentRole, TaskGraph, TaskNode, TaskRun


class ExecutionPlanner:
    """Derives ExecutionPlan.steps from a TaskGraph.

    P3-A: purely rule-based. Maps each TaskNode to a minimal dry-run step.
    No LLM. No real GitHub write.
    """

    TOOL_MAP: dict[str, str] = {
        # task_kind fragment → dry-run tool name
        "analyze":   "read_files",
        "research": "read_files",
        "produce":  "write_plan",
        "generate": "write_plan",
        "draft":    "write_plan",
        "review":   "review_plan",
        "assess":   "review_plan",
        "finalize": "write_plan",
        "deliver":  "generate_report",
        "default":  "noop",
    }

    def plan(self, task: TaskRun, graph: TaskGraph) -> ExecutionPlan:
        """Build an ExecutionPlan from a TaskRun and its TaskGraph."""
        plan = ExecutionPlan(task_id=task.task_id, dry_run=True)
        for i, node in enumerate(graph.nodes, start=1):
            step = self._node_to_step(i, node)
            plan.steps.append(step)

        # mark the last step as completion
        if plan.steps:
            plan.steps[-1].title = f"Complete: {plan.steps[-1].title}"
            plan.steps[-1].tool_name = "generate_report"

        plan.update_status("planned")
        return plan

    def _node_to_step(self, index: int, node: TaskNode) -> ExecutionStep:
        # pick tool based on description keyword
        tool_name = self._pick_tool(node.description, node.owner_agent)

        # step-level approval for high-risk individual steps
        step_risk = self._estimate_step_risk(node)
        requires_approval = step_risk in {"high", "critical"}

        return ExecutionStep(
            id=f"step_{index}",
            title=node.description,
            tool_name=tool_name,
            input={"task_node_id": node.id, "phase": node.phase},
            expected_output={"status": "dry_run"},
            requires_approval=requires_approval,
            risk_level=step_risk,
        )

    def _pick_tool(self, description: str, role: AgentRole) -> str:
        lower = description.lower()
        # pick the keyword that appears last in the description
        best_pos = -1
        best_tool = "noop"
        for keyword, tool in self.TOOL_MAP.items():
            if keyword == "default":
                continue
            pos = lower.find(keyword)
            if pos > best_pos:
                best_pos = pos
                best_tool = tool
        return best_tool

    def _estimate_step_risk(self, node: TaskNode) -> str:
        """Estimate risk level for a single step based on owner role."""
        if node.owner_agent == AgentRole.EXECUTOR:
            return "medium"
        return "low"