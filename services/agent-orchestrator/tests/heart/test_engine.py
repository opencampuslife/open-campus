"""P2-A tests for Heart Mode runtime MVP.

Covers:
  1. low-risk happy path → completed
  2. medium-risk → ready_for_approval
  3. high-risk → ready_for_approval
  4. critical-risk → blocked
  5. invalid goal → still generates generic graph
  6. event coverage: all expected event types present
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── make heart package importable ─────────────────────────────────────────
_HEART_SRC = Path(__file__).resolve().parents[2] / "src" / "heart"
if str(_HEART_SRC) not in sys.path:
    sys.path.insert(0, str(_HEART_SRC.parent))

from heart.engine import HeartEngine
from heart.events import EventType
from heart.models import TaskStatus
from heart.store import InMemoryHeartStore

# ── helpers ────────────────────────────────────────────────────────────────


def _event_types(events) -> list[str]:
    return [e.event_type for e in events]


# ── happy path: low risk ──────────────────────────────────────────────────


class TestLowRiskHappyPath:
    """Low risk tasks auto-complete through P2-A pipeline."""

    def test_feature_task(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Add Heart Mode runtime MVP", "low")
        assert task.status == TaskStatus.INTAKE

        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.COMPLETED  # low risk → auto-complete
        assert task.task_graph is not None
        assert task.task_graph.node_count == 5

        # graph metadata
        assert len(task.task_graph.edges) > 0
        for node in task.task_graph.nodes:
            assert node.id.startswith("tn_")
            assert node.phase >= 1
            assert node.description
            assert node.owner_agent.value in {
                "planner", "researcher", "engineer", "reviewer", "reporter"
            }

        # team
        assert task.team_assignment
        expected_roles = {"planner", "researcher", "engineer", "reviewer", "reporter"}
        assert set(task.team_assignment.keys()) == expected_roles

        # events
        events = engine.get_events(task.task_id)
        types = _event_types(events)
        assert EventType.TASK_CREATED.value in types
        assert EventType.INTAKE_COMPLETED.value in types
        assert EventType.PLANNING_STARTED.value in types
        assert EventType.PLAN_GENERATED.value in types
        assert EventType.TEAM_ASSEMBLED.value in types

    def test_fix_task(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Fix timeout in hybrid search", "low")
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.task_graph is not None
        assert task.task_graph.node_count == 5

    def test_docs_task(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Write the Heart Mode design document", "low")
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.task_graph is not None
        assert task.task_graph.node_count == 5

    def test_refactor_task(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Refactor knowledge service chunker", "low")
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.task_graph is not None
        assert task.task_graph.node_count == 5

    def test_generic_task(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Improve overall system performance", "low")
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.task_graph is not None
        assert task.task_graph.node_count == 5


# ── medium risk → ready_for_approval ──────────────────────────────────────


class TestMediumRiskApprovalRequired:
    def test_stops_at_ready_for_approval(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Add new CRM endpoint", "medium")
        task = engine.plan(task.task_id)

        assert task.status == TaskStatus.READY_FOR_APPROVAL
        assert task.task_graph is not None
        assert task.task_graph.node_count >= 3
        assert task.team_assignment

        events = engine.get_events(task.task_id)
        types = _event_types(events)
        assert EventType.APPROVAL_REQUIRED.value in types
        assert EventType.TASK_BLOCKED.value not in types
        assert EventType.TASK_FAILED.value not in types

    def test_medium_with_acceptance_criteria(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task(
            "Add auth middleware for admin API",
            "medium",
            acceptance_criteria=["All admin routes require JWT", "Token refresh works"],
        )
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.READY_FOR_APPROVAL
        assert len(task.acceptance_criteria) == 2


# ── high risk → ready_for_approval (but needs human oversight) ────────────


class TestHighRiskApprovalRequired:
    def test_stops_at_ready_for_approval(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Migrate database schema for CRM", "high")
        task = engine.plan(task.task_id)

        assert task.status == TaskStatus.READY_FOR_APPROVAL
        assert task.task_graph is not None

        events = engine.get_events(task.task_id)
        types = _event_types(events)
        assert EventType.APPROVAL_REQUIRED.value in types

    def test_high_risk_secrets_change(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Rotate production API keys", "high")
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.READY_FOR_APPROVAL


# ── critical risk → blocked ───────────────────────────────────────────────


class TestCriticalRiskBlocked:
    def test_blocked_immediately(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Change root permission logic in auth-service", "critical")
        task = engine.plan(task.task_id)

        assert task.status == TaskStatus.BLOCKED
        assert task.task_graph is None  # never reached planning

        events = engine.get_events(task.task_id)
        types = _event_types(events)
        assert EventType.TASK_BLOCKED.value in types
        assert EventType.PLAN_GENERATED.value not in types

    def test_critical_with_acceptance_criteria(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Deploy to production with auto-rollback", "critical",
                                  acceptance_criteria=["Zero downtime", "Auto-rollback on failure"])
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.BLOCKED


# ── event integrity ───────────────────────────────────────────────────────


class TestEventIntegrity:
    def test_all_events_have_required_fields(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Test event integrity", "low")
        task = engine.plan(task.task_id)
        events = engine.get_events(task.task_id)

        assert len(events) >= 5  # created, intake, planning_started, plan_generated, team_assembled
        for e in events:
            assert e.event_id
            assert e.task_id == task.task_id
            assert e.event_type
            assert e.timestamp
            assert e.agent in {
                "heart_engine", "planner", "researcher", "reviewer", "reporter"
            }


# ── idempotency ───────────────────────────────────────────────────────────


class TestIdempotentOperations:
    def test_plan_twice_no_side_effects(self):
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Idempotent test", "low")
        first = engine.plan(task.task_id)
        second = engine.plan(task.task_id)

        assert first.status == second.status
        assert first.task_graph.node_count == second.task_graph.node_count
        events = engine.get_events(task.task_id)
        # planning events should not duplicate
        plan_started_count = sum(
            1 for e in events if e.event_type == EventType.PLANNING_STARTED.value
        )
        assert plan_started_count == 1

    def test_get_task_unknown(self):
        engine = HeartEngine(InMemoryHeartStore())
        assert engine.get_task("task_nonexistent") is None

    def test_get_events_unknown(self):
        engine = HeartEngine(InMemoryHeartStore())
        assert engine.get_events("task_nonexistent") == []


# ── engine config ─────────────────────────────────────────────────────────


class TestEngineConfig:
    def test_default_in_memory_store(self):
        engine = HeartEngine()  # no store → auto-creates InMemoryHeartStore
        assert isinstance(engine.store, InMemoryHeartStore)

    def test_custom_store(self):
        store = InMemoryHeartStore()
        engine = HeartEngine(store)
        assert engine.store is store


# ── explicit approval override ────────────────────────────────────────────


class TestExplicitApprovalOverride:
    def test_low_risk_explicit_approval_required(self):
        """User can force approval even for low-risk tasks."""
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Add feature X", "low", requires_human_approval=True)
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.READY_FOR_APPROVAL

    def test_medium_risk_explicit_no_approval(self):
        """User can skip approval for medium-risk tasks (override)."""
        engine = HeartEngine(InMemoryHeartStore())
        task = engine.create_task("Fix search bug", "medium", requires_human_approval=False)
        task = engine.plan(task.task_id)
        assert task.status == TaskStatus.COMPLETED
