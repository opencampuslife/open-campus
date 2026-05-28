"""Risk-level and approval policies for Heart Mode.

P2-A: deterministic, rule-based. No LLM.
"""

from __future__ import annotations

from .models import RiskLevel, TaskStatus


def requires_approval(risk_level: RiskLevel) -> bool:
    """Does this risk level require human approval before execution?

    low      → auto-approved
    medium   → requires approval
    high     → requires approval + plan only (no auto-execution)
    critical → blocked (human-only)
    """
    return risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}


def can_auto_execute(risk_level: RiskLevel) -> bool:
    """Can this risk level proceed to execution after approval?"""
    return risk_level in {RiskLevel.LOW, RiskLevel.MEDIUM}


def allowed_next_states(current: TaskStatus) -> list[TaskStatus]:
    """Return valid next states from the current P2-A state.

    P2-A capped transitions:
        task_created    → intake
        intake          → planning | blocked
        planning        → team_formation | blocked | failed
        team_formation  → ready_for_approval | blocked | failed
        ready_for_approval → (terminal for P2-A)
    """
    _transitions: dict[TaskStatus, list[TaskStatus]] = {
        TaskStatus.TASK_CREATED: [TaskStatus.INTAKE],
        TaskStatus.INTAKE: [TaskStatus.PLANNING, TaskStatus.BLOCKED, TaskStatus.FAILED],
        TaskStatus.PLANNING: [TaskStatus.TEAM_FORMATION, TaskStatus.BLOCKED, TaskStatus.FAILED],
        TaskStatus.TEAM_FORMATION: [TaskStatus.READY_FOR_APPROVAL, TaskStatus.BLOCKED, TaskStatus.FAILED],
        # P2-B: execution is reachable from ready_for_approval via approval
        TaskStatus.READY_FOR_APPROVAL: [TaskStatus.EXECUTION, TaskStatus.BLOCKED, TaskStatus.CANCELLED],
        TaskStatus.EXECUTION: [TaskStatus.EVIDENCE_GATE, TaskStatus.BLOCKED, TaskStatus.FAILED],
        TaskStatus.EVIDENCE_GATE: [TaskStatus.COMPLETED, TaskStatus.BLOCKED],
    }
    return _transitions.get(current, [])


def is_valid_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in allowed_next_states(current)


def risk_blocked_state(risk_level: RiskLevel) -> TaskStatus:
    """Return the state a task should enter when risk blocks execution."""
    if risk_level == RiskLevel.CRITICAL:
        return TaskStatus.BLOCKED
    return TaskStatus.READY_FOR_APPROVAL
