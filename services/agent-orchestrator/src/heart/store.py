"""HeartStore: abstract base + in-memory implementation.

P2-A uses InMemoryHeartStore. P3-B adds SQLiteHeartStore (see store_sqlite.py).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Any, Optional

from .models import EvidenceEvent, TaskRun, now_iso


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class HeartStore(ABC):
    """Abstract storage for TaskRun and EvidenceEvent.

    P3-B extends this with approvals and execution plan persistence.
    """

    @abstractmethod
    def create_task(self, task: TaskRun) -> TaskRun:
        ...

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[TaskRun]:
        ...

    @abstractmethod
    def update_task(self, task: TaskRun) -> TaskRun:
        ...

    @abstractmethod
    def append_event(
        self,
        event: EvidenceEvent,
        idempotency_key: str | None = None,
    ) -> EvidenceEvent:
        """Append event, optionally deduplicated by idempotency_key.

        If idempotency_key is provided and a matching event already exists,
        returns the existing event without writing.
        """
        ...

    @abstractmethod
    def get_events(self, task_id: str) -> list[EvidenceEvent]:
        ...

    # ── P3-B: approvals ───────────────────────────────────────────────────────

    @abstractmethod
    def create_approval(
        self,
        task_id: str,
        decision: str,
        approved_by: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        """Record an approval decision. Returns the approval record dict.

        If idempotency_key is provided and already exists, returns existing record.
        """
        ...

    @abstractmethod
    def get_approvals(self, task_id: str) -> list[dict]:
        ...

    # ── P3-B: execution plans ────────────────────────────────────────────────

    @abstractmethod
    def save_execution_plan(
        self,
        task_id: str,
        plan_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        """Save an execution plan. Returns the saved record.

        If plan already exists for task_id, returns existing record.
        """
        ...

    @abstractmethod
    def get_execution_plan(self, task_id: str) -> Optional[dict]:
        ...

    # ── P3-C: delivery evidence ─────────────────────────────────────────────

    @abstractmethod
    def save_delivery_evidence(
        self,
        task_id: str,
        delivery_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        """Record a delivery evidence event (branch/PR/commit from apply_execution_plan).

        If delivery_id already exists for task_id, returns existing record.
        """
        ...

    @abstractmethod
    def get_delivery_evidence(self, task_id: str) -> list[dict]:
        """Get all delivery evidence records for a task."""
        ...


class InMemoryHeartStore(HeartStore):
    """Ephemeral, in-memory store for development and testing."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRun] = {}
        self._events: dict[str, list[EvidenceEvent]] = {}
        self._approvals: dict[str, list[dict]] = {}
        self._plans: dict[str, dict] = {}
        self._delivery: dict[str, list[dict]] = {}

    def create_task(self, task: TaskRun) -> TaskRun:
        task.task_id = task.task_id or _new_id("task")
        self._tasks[task.task_id] = task
        self._events.setdefault(task.task_id, [])
        self._approvals.setdefault(task.task_id, [])
        return task

    def get_task(self, task_id: str) -> Optional[TaskRun]:
        return self._tasks.get(task_id)

    def update_task(self, task: TaskRun) -> TaskRun:
        self._tasks[task.task_id] = task
        return task

    def append_event(
        self,
        event: EvidenceEvent,
        idempotency_key: str | None = None,
    ) -> EvidenceEvent:
        if idempotency_key:
            existing = [
                e for e in self._events.get(event.task_id, [])
                if e.idempotency_key == idempotency_key
            ]
            if existing:
                return existing[0]
        event.event_id = event.event_id or _new_id("evt")
        event.idempotency_key = idempotency_key
        self._events.setdefault(event.task_id, []).append(event)
        return event

    def get_events(self, task_id: str) -> list[EvidenceEvent]:
        return list(self._events.get(task_id, []))

    # ── P3-B ────────────────────────────────────────────────────────────────

    def create_approval(
        self,
        task_id: str,
        decision: str,
        approved_by: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        if idempotency_key:
            existing = [a for a in self._approvals.get(task_id, [])
                        if a.get("idempotency_key") == idempotency_key]
            if existing:
                return existing[0]
        record = {
            "id": _new_id("apr"),
            "task_id": task_id,
            "decision": decision,
            "approved_by": approved_by,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "created_at": now_iso(),
        }
        self._approvals.setdefault(task_id, []).append(record)
        return record

    def get_approvals(self, task_id: str) -> list[dict]:
        return list(self._approvals.get(task_id, []))

    def save_execution_plan(
        self,
        task_id: str,
        plan_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        if task_id in self._plans:
            return self._plans[task_id]
        record = {
            "task_id": task_id,
            "plan_id": plan_id,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self._plans[task_id] = record
        return record

    def get_execution_plan(self, task_id: str) -> Optional[dict]:
        return self._plans.get(task_id)

    # ── P3-C: delivery evidence ─────────────────────────────────────────────

    def save_delivery_evidence(
        self,
        task_id: str,
        delivery_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        if idempotency_key:
            existing = [d for d in self._delivery.get(task_id, [])
                        if d.get("idempotency_key") == idempotency_key]
            if existing:
                return existing[0]
        record = {
            "id": _new_id("del"),
            "task_id": task_id,
            "delivery_id": delivery_id,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "created_at": now_iso(),
        }
        self._delivery.setdefault(task_id, []).append(record)
        return record

    def get_delivery_evidence(self, task_id: str) -> list[dict]:
        return list(self._delivery.get(task_id, []))