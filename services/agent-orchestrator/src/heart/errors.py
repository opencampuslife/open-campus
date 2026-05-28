"""Heart Mode exception hierarchy."""

from __future__ import annotations


class HeartError(Exception):
    """Base exception for all Heart Mode errors."""
    pass


class TaskNotFound(HeartError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class InvalidTransition(HeartError):
    def __init__(
        self,
        task_id: str,
        current: str,
        target: str,
        reason: str | None = None,
    ) -> None:
        msg = f"Invalid state transition for task {task_id}: {current} → {target}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
        self.task_id = task_id
        self.current = current
        self.target = target
        self.reason = reason


class ApprovalRequired(HeartError):
    def __init__(self, task_id: str, reason: str | None = None) -> None:
        msg = f"Task {task_id} requires approval before execution"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.task_id = task_id


class ApprovalRejected(HeartError):
    def __init__(self, task_id: str, reason: str | None = None) -> None:
        msg = f"Approval rejected for task {task_id}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.task_id = task_id


class EvidenceGateFailed(HeartError):
    def __init__(self, task_id: str, issues: list[str]) -> None:
        super().__init__(f"Evidence gate failed for task {task_id}: {issues}")
        self.task_id = task_id
        self.issues = issues


class TaskAlreadyTerminal(HeartError):
    def __init__(self, task_id: str, status: str) -> None:
        super().__init__(f"Task {task_id} is already in terminal state: {status}")
        self.task_id = task_id
        self.status = status