"""Unit tests for HeartAPI adapter."""

from __future__ import annotations

import pytest

from heart.api import HeartAPI
from heart.errors import TaskNotFound, ApprovalRequired, ApprovalRejected
from heart.events import EventType
from heart.models import TaskStatus
from heart.store import InMemoryHeartStore


@pytest.fixture
def api():
    return HeartAPI(InMemoryHeartStore())


# ── create_task ───────────────────────────────────────────────────────────


class TestCreateTask:
    def test_returns_contract_compatible_dict(self, api):
        result = api.create_task({"goal": "Add Heart Mode runtime MVP"})
        assert "task_id" in result
        assert result["goal"] == "Add Heart Mode runtime MVP"
        assert result["risk_level"] == "low"
        assert result["status"] == TaskStatus.INTAKE.value
        assert result["created_at"]
        assert "team_assignment" in result

    def test_medium_risk(self, api):
        result = api.create_task({
            "goal": "Add new CRM endpoint",
            "risk_level": "medium",
            "acceptance_criteria": ["All admin routes require JWT"],
        })
        assert result["risk_level"] == "medium"
        assert result["acceptance_criteria"] == ["All admin routes require JWT"]

    def test_missing_goal_raises(self, api):
        with pytest.raises(ValueError, match="goal is required"):
            api.create_task({})

    def test_invalid_risk_level_raises(self, api):
        with pytest.raises(ValueError, match="invalid risk_level"):
            api.create_task({"goal": "Test", "risk_level": "super_high"})


# ── plan ─────────────────────────────────────────────────────────────────


class TestPlan:
    def test_plan_returns_task(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low"})
        result = api.plan(t["task_id"])
        assert result["status"] == TaskStatus.COMPLETED.value
        assert result["task_graph"] is not None
        assert result["task_graph"]["node_count"] == 5
        assert result["team_assignment"]

    def test_plan_unknown_task_raises(self, api):
        with pytest.raises(TaskNotFound):
            api.plan("task_nonexistent")


# ── get_task / get_events ────────────────────────────────────────────────


class TestQuery:
    def test_get_task(self, api):
        t = api.create_task({"goal": "Add feature"})
        result = api.get_task(t["task_id"])
        assert result["task_id"] == t["task_id"]

    def test_get_task_unknown(self, api):
        with pytest.raises(TaskNotFound):
            api.get_task("task_nonexistent")

    def test_get_events(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low"})
        t = api.plan(t["task_id"])
        result = api.get_events(t["task_id"])
        assert result["task_id"] == t["task_id"]
        assert len(result["events"]) >= 5
        for e in result["events"]:
            assert e["event_id"]
            assert e["event_type"]
            assert e["timestamp"]

    def test_get_events_unknown(self, api):
        with pytest.raises(TaskNotFound):
            api.get_events("task_nonexistent")


# ── approve_task ──────────────────────────────────────────────────────────


class TestApproveTask:
    def test_approve_creates_approval_event(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        assert t["status"] == TaskStatus.READY_FOR_APPROVAL.value

        t = api.approve_task(t["task_id"], {
            "decision": "approved",
            "approved_by": "admin",
            "reason": "looks good",
        })
        # approval does NOT change status; use plan_execution() to advance
        assert t["status"] == TaskStatus.READY_FOR_APPROVAL.value

        events = api.get_events(t["task_id"])
        types = [e["event_type"] for e in events["events"]]
        assert EventType.APPROVAL_GRANTED.value in types

    def test_reject_stays_in_ready(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        t = api.approve_task(t["task_id"], {
            "decision": "rejected",
            "approved_by": "admin",
            "reason": "needs revision",
        })
        assert t["status"] == TaskStatus.READY_FOR_APPROVAL.value

    def test_approve_without_plan_raises(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        with pytest.raises(ApprovalRequired):
            api.approve_task(t["task_id"], {
                "decision": "approved",
                "approved_by": "admin",
            })

    def test_missing_approved_by_raises(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        with pytest.raises(ValueError, match="approved_by is required"):
            api.approve_task(t["task_id"], {
                "decision": "approved",
            })

    def test_invalid_decision_raises(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        with pytest.raises(ValueError, match="invalid decision"):
            api.approve_task(t["task_id"], {
                "decision": "maybe",
                "approved_by": "admin",
            })


# ── cancel_task ──────────────────────────────────────────────────────────


class TestCancelTask:
    def test_cancel_intake(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.cancel_task(t["task_id"], {"reason": "scope changed"})
        assert t["status"] == TaskStatus.CANCELLED.value

        events = api.get_events(t["task_id"])
        types = [e["event_type"] for e in events["events"]]
        assert EventType.TASK_CANCELLED.value in types

    def test_cancel_planning(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        t = api.cancel_task(t["task_id"])
        assert t["status"] == TaskStatus.CANCELLED.value


# ── evaluate_gate ────────────────────────────────────────────────────────


class TestEvaluateGate:
    def test_low_risk_pass(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        decision = api.evaluate_gate(t["task_id"])
        assert decision.status == "pass"

    def test_medium_unapproved_needs_human(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        decision = api.evaluate_gate(t["task_id"])
        # missing approval → needs_human_review (single issue = needs_human_review)
        assert decision.status == "needs_human_review"

    def test_approved_task_pass(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Tests pass"]})
        t = api.plan(t["task_id"])
        t = api.approve_task(t["task_id"], {
            "decision": "approved",
            "approved_by": "admin",
        })
        decision = api.evaluate_gate(t["task_id"])
        assert decision.status == "pass"

    def test_nonexistent_task_raises(self, api):
        with pytest.raises(TaskNotFound):
            api.evaluate_gate("task_nonexistent")


# ── response shape ────────────────────────────────────────────────────────


class TestResponseShape:
    def test_task_has_all_required_fields(self, api):
        t = api.create_task({
            "goal": "Add feature",
            "risk_level": "medium",
            "acceptance_criteria": ["Tests pass"],
        })
        required = ["task_id", "goal", "risk_level", "status",
                    "created_at", "team_assignment", "acceptance_criteria"]
        for field in required:
            assert field in t, f"missing field: {field}"

    def test_events_have_required_fields(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "low"})
        t = api.plan(t["task_id"])
        result = api.get_events(t["task_id"])
        for e in result["events"]:
            for field in ["event_id", "event_type", "timestamp", "agent"]:
                assert field in e, f"missing field: {field} in event"