"""HeartEngine — P2-A runtime orchestrator.

Wires models → store → agents → policies into the P2-A pipeline:

    task_created → intake → planning → team_formation → ready_for_approval

P2-A约束：
- 不调用 LLM
- 不执行 GitHub 写操作
- 不创建 PR
- 最高状态走到 ready_for_approval（中高风险）或 completed（低风险 dry-run）
"""

from __future__ import annotations

from typing import Optional

from .agents.planner import PlannerAgent
from .events import EventType
from .models import (
    EvidenceEvent,
    RiskLevel,
    TaskRun,
    TaskStatus,
    now_iso,
)
from .policies import is_valid_transition, requires_approval, risk_blocked_state
from .store import HeartStore, InMemoryHeartStore
from .team import compose_team


class HeartEngine:
    """Orchestrates Heart Mode task lifecycle through P2-A states."""

    def __init__(self, store: HeartStore | None = None) -> None:
        self._store = store or InMemoryHeartStore()

    @property
    def store(self) -> HeartStore:
        return self._store

    # ── public API ────────────────────────────────────────────────────

    def create_task(
        self,
        goal: str,
        risk_level: str = "low",
        *,
        created_by: str = "system",
        acceptance_criteria: list[str] | None = None,
        requires_human_approval: bool | None = None,
    ) -> TaskRun:
        """Create a TaskRun and advance through intake immediately.

        If requires_human_approval is explicitly set, it overrides the
        risk-level-derived policy. When None (default), the risk level
        determines the approval requirement.
        """
        rl = RiskLevel(risk_level)
        task = TaskRun(
            task_id="",  # store assigns
            goal=goal,
            risk_level=rl,
            created_by=created_by,
            acceptance_criteria=acceptance_criteria or [],
            status=TaskStatus.TASK_CREATED,
            constraints={
                "requires_human_approval": requires_human_approval,
            },
        )
        task = self._store.create_task(task)
        self._record_event(task.task_id, EventType.TASK_CREATED, "heart_engine",
                           None, TaskStatus.TASK_CREATED.value)

        # intake
        if not is_valid_transition(task.status, TaskStatus.INTAKE):
            return self._block(task, f"invalid transition from {task.status.value}")

        task.update_status(TaskStatus.INTAKE)
        self._store.update_task(task)
        self._record_event(task.task_id, EventType.INTAKE_COMPLETED, "heart_engine",
                           TaskStatus.TASK_CREATED.value, TaskStatus.INTAKE.value)

        return task

    def plan(self, task_id: str) -> TaskRun:
        """Run PlannerAgent and attach a TaskGraph.

        Advances: intake → planning → team_formation (or blocked/failed).
        For critical-risk tasks: goes directly to blocked after intake.
        """
        task = self._require_task(task_id)

        # critical-risk tasks block at intake
        if task.risk_level == RiskLevel.CRITICAL:
            return self._block(task, "critical risk: execution blocked")

        # → planning
        if not is_valid_transition(task.status, TaskStatus.PLANNING):
            return task  # already past or blocked

        task.update_status(TaskStatus.PLANNING)
        self._store.update_task(task)
        self._record_event(task.task_id, EventType.PLANNING_STARTED, "heart_engine",
                           TaskStatus.INTAKE.value, TaskStatus.PLANNING.value)

        # run planner
        planner = PlannerAgent()
        result = planner.run(task)
        if not result.success:
            return self._fail(task, result.error or "planning failed")

        graph, kind = PlannerAgent.generate_graph(task.goal)
        task.task_graph = graph
        task.update_status(TaskStatus.TEAM_FORMATION)
        self._store.update_task(task)
        self._record_event(task.task_id, EventType.PLAN_GENERATED,
                           "planner", TaskStatus.PLANNING.value,
                           TaskStatus.TEAM_FORMATION.value,
                           data={"task_kind": kind, "node_count": graph.node_count})

        # → team_formation
        return self._form_team(task, kind)

    def form_team(self, task_id: str) -> TaskRun:
        """Compose agent team (if not already done by plan())."""
        task = self._require_task(task_id)
        if task.status not in (TaskStatus.TEAM_FORMATION,):
            return task

        kind = "generic"
        if task.task_graph:
            # infer kind from the PlannerAgent classification
            from .agents.planner import _classify_goal
            kind = _classify_goal(task.goal)

        return self._form_team(task, kind)

    def get_task(self, task_id: str) -> Optional[TaskRun]:
        return self._store.get_task(task_id)

    def get_events(self, task_id: str) -> list[EvidenceEvent]:
        return self._store.get_events(task_id)

    def plan_execution(self, task_id: str) -> TaskRun:
        """Run ExecutorAgent to generate ExecutionPlan (idempotent).

        Preconditions: task in ready_for_approval, approval_granted event exists,
        task_graph present, risk != critical.

        Idempotent semantics:
        - Already past execution (evidence_gate/completed/failed/cancelled) → return as-is
        - Already in execution state → return existing task (no re-run)
        - First call from ready_for_approval → full flow
        """
        from .agents.executor import ExecutorAgent
        from .errors import ApprovalRequired, InvalidTransition
        from .events import EventType
        from .execution import ExecutionPlan

        task = self._require_task(task_id)

        # ── idempotent: already past execution stage ──
        if task.status in {TaskStatus.EVIDENCE_GATE, TaskStatus.COMPLETED,
                           TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return task

        # ── idempotent: already in execution → return without re-run ──
        if task.status == TaskStatus.EXECUTION:
            return task

        # ── preconditions ──
        if task.status == TaskStatus.BLOCKED:
            raise InvalidTransition(
                task_id, task.status.value, "plan_execution",
                "task is blocked",
            )

        events = self._store.get_events(task_id)
        has_grant = any(e.event_type == EventType.APPROVAL_GRANTED.value for e in events)
        if not has_grant:
            raise ApprovalRequired(task_id, "no approval grant found")

        if task.risk_level == RiskLevel.CRITICAL:
            raise InvalidTransition(
                task_id, task.status.value, "plan_execution",
                "critical risk: execution not permitted",
            )

        if task.task_graph is None:
            return self._block(task, "no task_graph: plan() must be called first")

        # ── advance to execution state ──
        prev = task.status
        task.update_status(TaskStatus.EXECUTION)
        self._store.update_task(task)
        self._record_event(task_id, EventType.EXECUTION_STARTED,
                           "heart_engine", prev.value, task.status.value,
                           idempotency_key=f"exec_started_{task_id}")

        # ── run executor agent ──
        executor = ExecutorAgent()
        result = executor.run(task)
        if not result.success:
            return self._fail(task, result.error or "execution planning failed")

        plan: ExecutionPlan = executor.plan(task)

        # ── record execution_planned event (idempotent by plan id) ──
        self._record_event(task_id, EventType.EXECUTION_PLANNED,
                           "executor", task.status.value, task.status.value,
                           data={
                               "execution_plan": plan.to_dict(),
                               "step_count": plan.step_count,
                               "dry_run": plan.dry_run,
                           },
                           idempotency_key=f"exec_planned_{task_id}")

        # also persist to execution_plans table for apply_execution_plan retrieval
        self._store.save_execution_plan(
            task_id=task_id,
            plan_id=f"plan_{task_id}",
            payload=plan.to_dict(),
            idempotency_key=f"exec_planned_{task_id}",
        )

        # ── advance to evidence_gate ──
        task.update_status(TaskStatus.EVIDENCE_GATE)
        self._store.update_task(task)
        self._record_event(task_id, EventType.GATE_STARTED,
                           "heart_engine", TaskStatus.EXECUTION.value,
                           TaskStatus.EVIDENCE_GATE.value,
                           idempotency_key=f"gate_started_{task_id}")

        return task

    def complete_execution(self, task_id: str) -> TaskRun:
        """Advance task from EXECUTION to EVIDENCE_GATE (idempotent)."""
        task = self._require_task(task_id)
        if task.status == TaskStatus.EVIDENCE_GATE:
            return task  # already there
        if task.status != TaskStatus.EXECUTION:
            from .errors import InvalidTransition
            raise InvalidTransition(
                task_id, task.status.value, "complete_execution",
                "task must be in execution state",
            )
        prev = task.status
        task.update_status(TaskStatus.EVIDENCE_GATE)
        self._store.update_task(task)
        self._record_event(task_id, EventType.GATE_STARTED,
                           "heart_engine", prev.value, task.status.value,
                           idempotency_key=f"gate_started_{task_id}")
        return task

    def complete_gate(self, task_id: str) -> TaskRun:
        """Advance task from EVIDENCE_GATE to COMPLETED (idempotent)."""
        task = self._require_task(task_id)
        if task.status == TaskStatus.COMPLETED:
            return task  # already there
        if task.status not in {TaskStatus.EVIDENCE_GATE}:
            from .errors import InvalidTransition
            raise InvalidTransition(
                task_id, task.status.value, "complete_gate",
                "task must be in evidence_gate state",
            )
        prev = task.status
        task.update_status(TaskStatus.COMPLETED)
        self._store.update_task(task)
        self._record_event(task_id, EventType.TASK_COMPLETED,
                           "heart_engine", prev.value, task.status.value,
                           idempotency_key=f"task_completed_{task_id}")
        return task

    # ── internals ─────────────────────────────────────────────────────

    def _form_team(self, task: TaskRun, kind: str) -> TaskRun:
        """Internal: compose and attach team, then decide terminal state."""
        team = compose_team(task, kind)
        task.team_assignment = team["assignment"]
        self._store.update_task(task)
        self._record_event(task.task_id, EventType.TEAM_ASSEMBLED,
                           "heart_engine", TaskStatus.TEAM_FORMATION.value,
                           TaskStatus.TEAM_FORMATION.value,
                           data=team)

        # decide terminal state for P2-A
        explicit_approval = task.constraints.get("requires_human_approval")
        if explicit_approval is True:
            final = risk_blocked_state(task.risk_level)
            if final != TaskStatus.BLOCKED:
                final = TaskStatus.READY_FOR_APPROVAL
        elif explicit_approval is False:
            final = TaskStatus.COMPLETED
        elif requires_approval(task.risk_level):
            final = risk_blocked_state(task.risk_level)
        else:
            final = TaskStatus.COMPLETED

        task.update_status(final)
        self._store.update_task(task)

        event_type = EventType.TASK_BLOCKED if final == TaskStatus.BLOCKED else EventType.APPROVAL_REQUIRED
        self._record_event(task.task_id, event_type, "heart_engine",
                           TaskStatus.TEAM_FORMATION.value, final.value)

        return task

    def _record_event(
        self,
        task_id: str,
        event_type: EventType,
        agent: str,
        previous_state: str | None,
        new_state: str | None,
        *,
        data: dict | None = None,
        error: str | None = None,
        idempotency_key: str | None = None,
    ) -> EvidenceEvent:
        event = EvidenceEvent(
            event_id="",  # store assigns
            task_id=task_id,
            event_type=event_type.value,
            timestamp=now_iso(),
            agent=agent,
            previous_state=previous_state,
            new_state=new_state,
            data=data,
            error=error,
        )
        return self._store.append_event(event, idempotency_key=idempotency_key)

    def _require_task(self, task_id: str) -> TaskRun:
        task = self._store.get_task(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")
        return task

    def _block(self, task: TaskRun, reason: str) -> TaskRun:
        prev = task.status.value
        task.update_status(TaskStatus.BLOCKED)
        self._store.update_task(task)
        self._record_event(task.task_id, EventType.TASK_BLOCKED, "heart_engine",
                           prev, TaskStatus.BLOCKED.value, data={"reason": reason})
        return task

    def _fail(self, task: TaskRun, reason: str) -> TaskRun:
        prev = task.status.value
        task.update_status(TaskStatus.FAILED)
        self._store.update_task(task)
        self._record_event(task.task_id, EventType.TASK_FAILED, "heart_engine",
                           prev, TaskStatus.FAILED.value, error=reason)
        return task
