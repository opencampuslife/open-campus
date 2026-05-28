"""TeamComposer — picks the right agent team for a task.

P2-A: deterministic, based on task kind + risk_level.
"""

from __future__ import annotations

from typing import Any

from .models import AgentRole, RiskLevel, TaskRun


def compose_team(task: TaskRun, task_kind: str) -> dict[str, Any]:
    """Return the agent team assignment for a task.

    Returns:
        {
            "roles": [AgentRole, ...],
            "assignment": {role.value: "assigned"},
            "requires_executor": bool,
        }

    P2-A never assigns ExecutorAgent (no GitHub write).
    """

    # ── base team: always planner + researcher + reviewer + reporter ──
    roles: list[AgentRole] = [
        AgentRole.PLANNER,
        AgentRole.RESEARCHER,
        AgentRole.REVIEWER,
        AgentRole.REPORTER,
    ]

    # engineer is included for feature/fix/refactor tasks
    if task_kind in ("feature", "fix", "refactor", "generic"):
        roles.insert(2, AgentRole.ENGINEER)

    # executor is NOT assigned in P2-A (no write capability)
    requires_executor = False

    if task.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
        requires_executor = True  # will need executor, but assignment deferred to P2-B

    assignment: dict[str, str] = {}
    for role in roles:
        assignment[role.value] = "assigned"

    return {
        "roles": [r.value for r in roles],
        "assignment": assignment,
        "requires_executor": requires_executor,
        "task_kind": task_kind,
    }
