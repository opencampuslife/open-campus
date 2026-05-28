"""Event types and event recording for Heart Mode audit trail.

Matches contracts/schemas/heart-event.schema.json EventType enum.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class EventType(str, Enum):
    # ── lifecycle events ──
    TASK_CREATED = "task_created"
    INTAKE_COMPLETED = "intake_completed"
    PLANNING_STARTED = "planning_started"
    PLAN_GENERATED = "plan_generated"
    TEAM_ASSEMBLED = "team_assembled"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    EXECUTION_STARTED = "execution_started"
    TOOL_CALL = "tool_call"
    EXECUTION_COMPLETED = "execution_completed"
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    GATE_STARTED = "gate_started"
    GATE_RESULT = "gate_result"
    # ── terminal events ──
    TASK_COMPLETED = "task_completed"
    TASK_BLOCKED = "task_blocked"
    TASK_FAILED = "task_failed"
    NEEDS_HUMAN = "needs_human"
    # ── repair events (P4) ──
    REPAIR_STARTED = "repair_started"
    REPAIR_COMPLETED = "repair_completed"
    TASK_CANCELLED = "task_cancelled"
    EXECUTION_PLANNED = "execution_planned"
    DRY_RUN_STARTED = "dry_run_started"
    DRY_RUN_COMPLETED = "dry_run_completed"


# ── P2-A event set ────────────────────────────────────────────────────────

P2A_VISIBLE_EVENTS: set[EventType] = {
    EventType.TASK_CREATED,
    EventType.INTAKE_COMPLETED,
    EventType.PLANNING_STARTED,
    EventType.PLAN_GENERATED,
    EventType.TEAM_ASSEMBLED,
    EventType.APPROVAL_REQUIRED,
    EventType.TASK_BLOCKED,
    EventType.TASK_FAILED,
}
