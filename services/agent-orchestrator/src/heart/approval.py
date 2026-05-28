"""ApprovalGate — approve / cancel / pause / resume semantics.

P2-B scope: state machine validation + event emission only.
No real GitHub write. No CI run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import (
    ApprovalRejected,
    ApprovalRequired,
    InvalidTransition,
    TaskAlreadyTerminal,
    TaskNotFound,
)
from .events import EventType
from .models import RiskLevel, TaskRun, TaskStatus, now_iso
from .policies import is_valid_transition
from .store import HeartStore


@dataclass
class ApprovalRequest:
    decision: str          # "approved" | "rejected" | "modified"
    approved_by: str       # human approver identifier
    reason: str | None = None
    modifications: list[str] = field(default_factory=list)
    idempotency_key: str | None = None


# ── ApprovalGate ──────────────────────────────────────────────────────────


class ApprovalGate:
    """Validates approval requests and advances task state."""

    def __init__(self, store: HeartStore) -> None:
        self._store = store

    def can_approve(self, task_id: str) -> tuple[bool, str | None]:
        """Return (can_approve, reason_if_not)."""
        task = self._store.get_task(task_id)
        if task is None:
            return False, "task not found"

        if task.status == TaskStatus.BLOCKED:
            return False, f"task is blocked"

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        if task.status in terminal:
            return False, f"task is already {task.status.value}"

        if task.status != TaskStatus.READY_FOR_APPROVAL:
            return False, f"task must be in ready_for_approval state, got {task.status.value}"

        if task.task_graph is None:
            return False, "no plan exists; plan must be generated before approval"

        # critical risk tasks: never advance to execution, only to planning-only
        if task.risk_level == RiskLevel.CRITICAL:
            return False, "critical risk tasks cannot be approved for execution"

        return True, None

    def grant(
        self,
        task_id: str,
        request: ApprovalRequest,
    ) -> TaskRun:
        """Approve a task — record the approval event but do NOT advance state.

        State advancement is the responsibility of plan_execution().
        """
        ok, reason = self.can_approve(task_id)
        if not ok:
            raise ApprovalRequired(task_id, reason)

        task = self._store.get_task(task_id)
        assert task is not None

        prev = task.status
        self._store.append_event(
            self._build_event(task.task_id, EventType.APPROVAL_GRANTED, prev.value, prev.value,
                              {"approved_by": request.approved_by,
                               "reason": request.reason or "",
                               "modifications": request.modifications}),
            idempotency_key=request.idempotency_key,
        )
        # also persist to approvals table so apply_execution_plan can query it
        self._store.create_approval(
            task_id=task_id,
            decision="approved",
            approved_by=request.approved_by,
            payload={
                "reason": request.reason or "",
                "modifications": request.modifications,
            },
            idempotency_key=request.idempotency_key,
        )

        return task

    def reject(
        self,
        task_id: str,
        request: ApprovalRequest,
    ) -> TaskRun:
        """Reject a task — records rejection, does not change task state."""
        task = self._store.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)

        ok, reason = self.can_approve(task_id)
        if not ok:
            raise ApprovalRejected(task_id, reason)

        prev = task.status
        self._store.append_event(
            self._build_event(task.task_id, EventType.APPROVAL_REJECTED, prev.value, prev.value,
                              {"rejected_by": request.approved_by,
                               "reason": request.reason or ""}),
            idempotency_key=request.idempotency_key,
        )

        return task

    def cancel(
        self,
        task_id: str,
        cancelled_by: str = "system",
        reason: str | None = None,
    ) -> TaskRun:
        """Cancel a task from any non-terminal state."""
        task = self._store.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        if task.status in terminal:
            raise TaskAlreadyTerminal(task_id, task.status.value)

        prev = task.status
        task.update_status(TaskStatus.CANCELLED)
        self._store.update_task(task)

        self._store.append_event(
            self._build_event(task.task_id, EventType.TASK_CANCELLED, prev.value, TaskStatus.CANCELLED.value,
                              {"cancelled_by": cancelled_by, "reason": reason or ""})
        )

        return task

    def _build_event(
        self,
        task_id: str,
        event_type: EventType,
        prev: str,
        new: str,
        data: dict | None = None,
    ):
        from .models import EvidenceEvent
        return EvidenceEvent(
            event_id="",
            task_id=task_id,
            event_type=event_type.value,
            timestamp=now_iso(),
            agent="heart_engine",
            previous_state=prev,
            new_state=new,
            data=data,
        )