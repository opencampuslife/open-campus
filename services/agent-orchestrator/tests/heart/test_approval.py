"""Unit tests for ApprovalGate and evidence_gate."""

from __future__ import annotations

import pytest

from heart.approval import ApprovalGate, ApprovalRequest
from heart.engine import HeartEngine
from heart.errors import ApprovalRequired, ApprovalRejected, TaskAlreadyTerminal, TaskNotFound
from heart.events import EventType
from heart.evidence_gate import EvidenceGate
from heart.models import TaskStatus
from heart.store import InMemoryHeartStore


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def api():
    from heart.api import HeartAPI
    return HeartAPI(InMemoryHeartStore())


@pytest.fixture
def approved_task(api):
    """Create and approve a medium-risk task.

    Note: approval does NOT change state; task remains in ready_for_approval.
    Use plan_execution() to advance to execution.
    """
    t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                         "acceptance_criteria": ["Tests pass"]})
    t = api.plan(t["task_id"])
    t = api.approve_task(t["task_id"], {
        "decision": "approved",
        "approved_by": "admin",
        "reason": "looks good",
    })
    return t


# ── approval: approve_task ────────────────────────────────────────────────


class TestApproveTask:
    def test_approval_records_event(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium"})
        t = api.plan(t["task_id"])
        assert t["status"] == TaskStatus.READY_FOR_APPROVAL.value

        t = api.approve_task(t["task_id"], {
            "decision": "approved",
            "approved_by": "admin",
        })
        # approval does NOT change status
        assert t["status"] == TaskStatus.READY_FOR_APPROVAL.value

        events = api.get_events(t["task_id"])["events"]
        types = [e["event_type"] for e in events]
        assert EventType.APPROVAL_GRANTED.value in types

    def test_approved_task_can_plan_execution(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                            "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        t = api.approve_task(t["task_id"], {
            "decision": "approved",
            "approved_by": "admin",
        })
        # approval does NOT change status; plan_execution advances
        assert t["status"] == TaskStatus.READY_FOR_APPROVAL.value
        result = api.plan_execution(t["task_id"])
        assert result["status"] == TaskStatus.EVIDENCE_GATE.value


# ── evidence gate ──────────────────────────────────────────────────────────


class TestEvidenceGate:
    def test_low_risk_auto_pass(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "pass"
        assert len(decision.blocking_issues) == 0

    def test_medium_risk_no_approval_blocked(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium"})
        t = api.plan(t["task_id"])
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        # medium risk needs approval but has none → needs_human_review
        assert decision.status == "needs_human_review"
        assert "missing_approval" in decision.blocking_issues

    def test_approved_task_pass(self, api, approved_task):
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(approved_task["task_id"])
        assert decision.status == "pass"
        assert len(decision.blocking_issues) == 0

    def test_critical_risk_blocked(self, api):
        t = api.create_task({"goal": "Deploy to prod", "risk_level": "critical"})
        api.plan(t["task_id"])
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "blocked"
        assert "critical_risk_blocked" in decision.blocking_issues

    def test_no_plan_blocked(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low"})
        # don't call plan()
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "blocked"
        assert "no_task_graph" in decision.blocking_issues

    def test_nonexistent_task_blocked(self, api):
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate("task_nonexistent")
        assert decision.status == "blocked"
        assert "task_not_found" in decision.blocking_issues

    def test_all_checks_present(self, api, approved_task):
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(approved_task["task_id"])
        names = {c.name for c in decision.checks}
        expected = {
            "task_exists", "task_graph_exists", "team_assembled",
            "acceptance_criteria_present", "approval_satisfied", "no_blocking_risk",
        }
        assert expected.issubset(names)