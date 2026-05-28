"""Unit tests for EvidenceGate."""

from __future__ import annotations

import pytest

from heart.api import HeartAPI
from heart.evidence_gate import EvidenceGate
from heart.models import TaskStatus
from heart.store import InMemoryHeartStore


@pytest.fixture
def api():
    return HeartAPI(InMemoryHeartStore())


class TestEvidenceGatePass:
    def test_low_risk_auto_complete(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "pass"
        assert decision.blocking_issues == []

    def test_approved_medium_task(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        t = api.approve_task(t["task_id"], {
            "decision": "approved",
            "approved_by": "admin",
        })
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "pass"


class TestEvidenceGateBlocked:
    def test_missing_approval(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "needs_human_review"
        assert "missing_approval" in decision.blocking_issues

    def test_critical_risk_blocked(self, api):
        t = api.create_task({"goal": "Deploy to prod", "risk_level": "critical",
                             "acceptance_criteria": ["Zero downtime"]})
        t = api.plan(t["task_id"])
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "blocked"
        assert "critical_risk_blocked" in decision.blocking_issues

    def test_no_graph_blocked(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low",
                             "acceptance_criteria": ["Tests pass"]})
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "blocked"
        assert "no_task_graph" in decision.blocking_issues

    def test_no_team_blocked(self, api):
        # No-team scenario: task exists but team not yet assigned
        # (low risk plan() always assigns team, so this tests the gate check directly)
        t = api.create_task({"goal": "Add feature", "risk_level": "low",
                             "acceptance_criteria": ["Tests pass"]})
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        # without plan(), task_graph and team are both absent → blocked
        assert decision.status == "blocked"
        assert "no_task_graph" in decision.blocking_issues

    def test_no_acceptance_criteria_blocked(self, api):
        # acceptance_criteria not provided → None → blocked by evidence gate
        t = api.create_task({"goal": "Add feature", "risk_level": "low"})
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        assert decision.status == "blocked"

    def test_nonexistent_task(self, api):
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate("task_nonexistent")
        assert decision.status == "blocked"
        assert "task_not_found" in decision.blocking_issues

    def test_check_names_complete(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        t = api.approve_task(t["task_id"], {
            "decision": "approved",
            "approved_by": "admin",
        })
        gate = EvidenceGate(api._engine.store)
        decision = gate.evaluate(t["task_id"])
        names = [c.name for c in decision.checks]
        assert "task_exists" in names
        assert "task_graph_exists" in names
        assert "team_assembled" in names
        assert "acceptance_criteria_present" in names
        assert "approval_satisfied" in names
        assert "no_blocking_risk" in names