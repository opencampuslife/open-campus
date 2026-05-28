"""Contract tests for HeartStore implementations.

Tests both InMemoryHeartStore and SQLiteHeartStore against the same
interface contract, ensuring implementations are interchangeable.
"""

from __future__ import annotations

import uuid

import pytest

from heart.models import (
    AgentRole,
    EvidenceEvent,
    RiskLevel,
    TaskGraph,
    TaskNode,
    TaskRun,
    TaskStatus,
)
from heart.store import InMemoryHeartStore
from heart.store_sqlite import SQLiteHeartStore


def make_task(task_id: str | None = None, goal: str = "Test task") -> TaskRun:
    return TaskRun(
        task_id=task_id or f"task_{uuid.uuid4().hex[:8]}",
        goal=goal,
        risk_level=RiskLevel.MEDIUM,
    )


def make_event(task_id: str, event_type: str = "test_event") -> EvidenceEvent:
    return EvidenceEvent(
        event_id="",
        task_id=task_id,
        event_type=event_type,
        timestamp="",
        agent="test",
        previous_state=None,
        new_state=None,
        data={"test": True},
    )


# ── InMemory store contract tests ───────────────────────────────────────────

class TestInMemoryContract:
    """All contract tests against InMemoryHeartStore."""

    @pytest.fixture
    def store(self):
        return InMemoryHeartStore()

    def test_create_and_get_task(self, store):
        task = make_task()
        created = store.create_task(task)
        assert created.task_id == task.task_id
        assert store.get_task(task.task_id) is not None
        assert store.get_task(task.task_id).goal == task.goal

    def test_update_task(self, store):
        task = store.create_task(make_task())
        task.goal = "Updated"
        store.update_task(task)
        assert store.get_task(task.task_id).goal == "Updated"

    def test_get_nonexistent_task(self, store):
        assert store.get_task("nonexistent") is None

    def test_create_task_with_graph(self, store):
        task = make_task()
        task.task_graph = TaskGraph(
            nodes=[TaskNode(id="tn_1", phase=1, description="Step",
                            owner_agent=AgentRole.PLANNER)],
            edges=[{"from": "tn_1", "to": "tn_2"}],
            version=1,
        )
        store.create_task(task)
        retrieved = store.get_task(task.task_id)
        assert retrieved.task_graph is not None
        assert retrieved.task_graph.node_count == 1

    def test_update_task_graph(self, store):
        task = store.create_task(make_task())
        task.task_graph = TaskGraph(
            nodes=[TaskNode(id="tn_x", phase=1, description="New",
                            owner_agent=AgentRole.REVIEWER)],
            version=1,
        )
        store.update_task(task)
        assert store.get_task(task.task_id).task_graph.node_count == 1

    def test_append_and_get_events(self, store):
        task = store.create_task(make_task())
        event = make_event(task.task_id, "step_completed")
        stored = store.append_event(event)
        assert stored.event_id
        events = store.get_events(task.task_id)
        assert len(events) == 1
        assert events[0].event_type == "step_completed"

    def test_get_events_empty(self, store):
        assert store.get_events("nonexistent") == []

    def test_multiple_events_ordered(self, store):
        task = store.create_task(make_task())
        for i in range(3):
            store.append_event(make_event(task.task_id, f"event_{i}"))
        events = store.get_events(task.task_id)
        assert len(events) == 3

    def test_append_event_idempotency_key_dedupes(self, store):
        task = store.create_task(make_task())
        key = f"dedup_{uuid.uuid4().hex[:8]}"

        event1 = make_event(task.task_id, "unique")
        stored1 = store.append_event(event1, idempotency_key=key)
        event2 = make_event(task.task_id, "unique")
        stored2 = store.append_event(event2, idempotency_key=key)

        assert stored1.event_id == stored2.event_id
        assert len(store.get_events(task.task_id)) == 1

    def test_append_event_without_key_allows_duplicates(self, store):
        task = store.create_task(make_task())
        store.append_event(make_event(task.task_id, "type_a"))
        store.append_event(make_event(task.task_id, "type_a"))
        assert len(store.get_events(task.task_id)) == 2

    def test_create_and_get_approval(self, store):
        task = store.create_task(make_task())
        record = store.create_approval(
            task.task_id, "approved", "admin", {"reason": "ok"},
        )
        assert record["id"]
        assert len(store.get_approvals(task.task_id)) == 1

    def test_multiple_approvals(self, store):
        task = store.create_task(make_task())
        store.create_approval(task.task_id, "approved", "admin", {})
        store.create_approval(task.task_id, "rejected", "mgr", {})
        assert len(store.get_approvals(task.task_id)) == 2

    def test_approval_idempotency_key(self, store):
        task = store.create_task(make_task())
        key = f"appr_idem_{uuid.uuid4().hex[:8]}"

        r1 = store.create_approval(task.task_id, "approved", "admin",
                                    {"reason": "first"}, idempotency_key=key)
        r2 = store.create_approval(task.task_id, "approved", "admin",
                                    {"reason": "second"}, idempotency_key=key)
        assert r1["id"] == r2["id"]
        assert len(store.get_approvals(task.task_id)) == 1

    def test_save_and_get_execution_plan(self, store):
        task = store.create_task(make_task())
        saved = store.save_execution_plan(
            task.task_id, "plan_001", {"steps": [], "dry_run": True},
        )
        assert saved["plan_id"] == "plan_001"
        assert saved["payload"]["dry_run"] is True

    def test_execution_plan_idempotent(self, store):
        task = store.create_task(make_task())
        key = f"plan_idem_{uuid.uuid4().hex[:8]}"

        r1 = store.save_execution_plan(task.task_id, "plan_A",
                                        {"step_count": 3}, idempotency_key=key)
        r2 = store.save_execution_plan(task.task_id, "plan_B",
                                        {"step_count": 10}, idempotency_key=key)
        assert r1["plan_id"] == r2["plan_id"]
        assert r2["payload"]["step_count"] == 3  # first plan kept

    def test_get_execution_plan_nonexistent(self, store):
        assert store.get_execution_plan("nonexistent") is None


# ── SQLite store contract tests (same assertions, different fixture) ───────

class TestSQLiteContract:
    """All contract tests against SQLiteHeartStore."""

    @pytest.fixture
    def store(self, tmp_path):
        db = tmp_path / "contract.db"
        store = SQLiteHeartStore(str(db))
        yield store
        try:
            db.unlink()
        except Exception:
            pass

    def test_create_and_get_task(self, store):
        task = make_task()
        created = store.create_task(task)
        assert created.task_id == task.task_id
        assert store.get_task(task.task_id) is not None
        assert store.get_task(task.task_id).goal == task.goal

    def test_update_task(self, store):
        task = store.create_task(make_task())
        task.goal = "Updated"
        store.update_task(task)
        assert store.get_task(task.task_id).goal == "Updated"

    def test_get_nonexistent_task(self, store):
        assert store.get_task("nonexistent") is None

    def test_create_task_with_graph(self, store):
        task = make_task()
        task.task_graph = TaskGraph(
            nodes=[TaskNode(id="tn_1", phase=1, description="Step",
                            owner_agent=AgentRole.PLANNER)],
            edges=[{"from": "tn_1", "to": "tn_2"}],
            version=1,
        )
        store.create_task(task)
        retrieved = store.get_task(task.task_id)
        assert retrieved.task_graph is not None
        assert retrieved.task_graph.node_count == 1

    def test_update_task_graph(self, store):
        task = store.create_task(make_task())
        task.task_graph = TaskGraph(
            nodes=[TaskNode(id="tn_x", phase=1, description="New",
                            owner_agent=AgentRole.REVIEWER)],
            version=1,
        )
        store.update_task(task)
        assert store.get_task(task.task_id).task_graph.node_count == 1

    def test_append_and_get_events(self, store):
        task = store.create_task(make_task())
        event = make_event(task.task_id, "step_completed")
        stored = store.append_event(event)
        assert stored.event_id
        events = store.get_events(task.task_id)
        assert len(events) == 1
        assert events[0].event_type == "step_completed"

    def test_get_events_empty(self, store):
        assert store.get_events("nonexistent") == []

    def test_multiple_events_ordered(self, store):
        task = store.create_task(make_task())
        for i in range(3):
            store.append_event(make_event(task.task_id, f"event_{i}"))
        events = store.get_events(task.task_id)
        assert len(events) == 3

    def test_append_event_idempotency_key_dedupes(self, store):
        task = store.create_task(make_task())
        key = f"dedup_{uuid.uuid4().hex[:8]}"

        event1 = make_event(task.task_id, "unique")
        stored1 = store.append_event(event1, idempotency_key=key)
        event2 = make_event(task.task_id, "unique")
        stored2 = store.append_event(event2, idempotency_key=key)

        assert stored1.event_id == stored2.event_id
        assert len(store.get_events(task.task_id)) == 1

    def test_append_event_without_key_allows_duplicates(self, store):
        task = store.create_task(make_task())
        store.append_event(make_event(task.task_id, "type_a"))
        store.append_event(make_event(task.task_id, "type_a"))
        assert len(store.get_events(task.task_id)) == 2

    def test_create_and_get_approval(self, store):
        task = store.create_task(make_task())
        record = store.create_approval(
            task.task_id, "approved", "admin", {"reason": "ok"},
        )
        assert record["id"]
        assert len(store.get_approvals(task.task_id)) == 1

    def test_multiple_approvals(self, store):
        task = store.create_task(make_task())
        store.create_approval(task.task_id, "approved", "admin", {})
        store.create_approval(task.task_id, "rejected", "mgr", {})
        assert len(store.get_approvals(task.task_id)) == 2

    def test_approval_idempotency_key(self, store):
        task = store.create_task(make_task())
        key = f"appr_idem_{uuid.uuid4().hex[:8]}"

        r1 = store.create_approval(task.task_id, "approved", "admin",
                                    {"reason": "first"}, idempotency_key=key)
        r2 = store.create_approval(task.task_id, "approved", "admin",
                                    {"reason": "second"}, idempotency_key=key)
        assert r1["id"] == r2["id"]
        assert len(store.get_approvals(task.task_id)) == 1

    def test_save_and_get_execution_plan(self, store):
        task = store.create_task(make_task())
        saved = store.save_execution_plan(
            task.task_id, "plan_001", {"steps": [], "dry_run": True},
        )
        assert saved["plan_id"] == "plan_001"
        assert saved["payload"]["dry_run"] is True

    def test_execution_plan_idempotent(self, store):
        task = store.create_task(make_task())
        key = f"plan_idem_{uuid.uuid4().hex[:8]}"

        r1 = store.save_execution_plan(task.task_id, "plan_A",
                                        {"step_count": 3}, idempotency_key=key)
        r2 = store.save_execution_plan(task.task_id, "plan_B",
                                        {"step_count": 10}, idempotency_key=key)
        assert r1["plan_id"] == r2["plan_id"]
        assert r2["payload"]["step_count"] == 3  # first plan kept

    def test_get_execution_plan_nonexistent(self, store):
        assert store.get_execution_plan("nonexistent") is None


# ── SQLite recovery tests ───────────────────────────────────────────────────

class TestSQLiteRecovery:
    """Test SQLite store survives file re-open (simulates crash recovery)."""

    @pytest.fixture
    def db_path(self, tmp_path):
        p = tmp_path / "heart_recovery.db"
        yield str(p)
        try:
            p.unlink()
        except Exception:
            pass

    def test_sqlite_store_persists_task_after_reopen(self, db_path):
        store1 = SQLiteHeartStore(db_path)
        task = make_task("recovery_task_1")
        store1.create_task(task)

        store2 = SQLiteHeartStore(db_path)
        retrieved = store2.get_task("recovery_task_1")
        assert retrieved is not None
        assert retrieved.goal == task.goal

    def test_sqlite_store_persists_events_after_reopen(self, db_path):
        store1 = SQLiteHeartStore(db_path)
        task = store1.create_task(make_task())
        store1.append_event(make_event(task.task_id, "recovery_event"))

        store2 = SQLiteHeartStore(db_path)
        events = store2.get_events(task.task_id)
        assert len(events) == 1
        assert events[0].event_type == "recovery_event"

    def test_sqlite_store_persists_approval_after_reopen(self, db_path):
        store1 = SQLiteHeartStore(db_path)
        task = store1.create_task(make_task())
        store1.create_approval(task.task_id, "approved", "admin", {})

        store2 = SQLiteHeartStore(db_path)
        approvals = store2.get_approvals(task.task_id)
        assert len(approvals) == 1
        assert approvals[0]["decision"] == "approved"

    def test_sqlite_store_persists_execution_plan_after_reopen(self, db_path):
        store1 = SQLiteHeartStore(db_path)
        task = store1.create_task(make_task())
        store1.save_execution_plan(task.task_id, "plan_v1", {"dry_run": True})

        store2 = SQLiteHeartStore(db_path)
        plan = store2.get_execution_plan(task.task_id)
        assert plan is not None
        assert plan["plan_id"] == "plan_v1"

    def test_sqlite_store_persists_task_graph_after_reopen(self, db_path):
        store1 = SQLiteHeartStore(db_path)
        task = make_task("recovery_graph_task")
        task.task_graph = TaskGraph(
            nodes=[TaskNode(id="tn_recovery", phase=1, description="Recovered",
                            owner_agent=AgentRole.ENGINEER)],
            version=1,
        )
        store1.create_task(task)

        store2 = SQLiteHeartStore(db_path)
        retrieved = store2.get_task("recovery_graph_task")
        assert retrieved.task_graph is not None
        assert retrieved.task_graph.node_count == 1

    def test_sqlite_execution_plan_idempotency_prevents_overwrite(self, db_path):
        """Second save_execution_plan with same key must preserve first plan."""
        store1 = SQLiteHeartStore(db_path)
        task = store1.create_task(make_task())
        key = f"plan_exec_{task.task_id}"

        r1 = store1.save_execution_plan(task.task_id, "plan_first",
                                         {"step_count": 3}, idempotency_key=key)
        r2 = store1.save_execution_plan(task.task_id, "plan_second",
                                         {"step_count": 10}, idempotency_key=key)

        assert r1["plan_id"] == r2["plan_id"]
        assert r2["plan_id"] == "plan_first"
        assert r2["payload"]["step_count"] == 3

        store2 = SQLiteHeartStore(db_path)
        plan = store2.get_execution_plan(task.task_id)
        assert plan["plan_id"] == "plan_first"
        assert plan["payload"]["step_count"] == 3