"""End-to-end tests for P3-E provider safety evidence.

Validates that apply_execution_plan() emits correct safety_events
in the right sequence, and that get_audit_report() reconstructs them.

P3-E验收:
1. apply_execution_plan() records provider_selected
2. WriteGuard pass records write_guard_passed
3. WriteGuard block records write_guard_blocked (no provider called)
4. branch/commit/PR each emit normalized evidence
5. get_audit_report() builds stable report
6. P3-E does NOT change TaskStatus
"""

from __future__ import annotations

import pytest

from heart.api import HeartAPI
from heart.audit import AuditStatus
from heart.models import AgentRole, TaskGraph, TaskNode, TaskNodeStatus, TaskStatus
from heart.store import InMemoryHeartStore
from heart.safety_events import SafetyEventType


def _run_to_evidence_gate(api: HeartAPI) -> dict:
    """Advance a low-risk task through to evidence_gate state.

    NOTE: P2 engine's plan() auto-completes all phases for low-risk tasks.
    We bypass the full plan flow by directly setting up the minimal preconditions.
    """
    t = api.create_task({
        "goal": "Test P3-E safety events",
        "risk_level": "low",
    })
    store = api._engine.store
    task = store.get_task(t["task_id"])

    # Set task_graph so plan_execution doesn't block
    task.task_graph = TaskGraph(
        nodes=[TaskNode(
            id="test_node",
            phase=1,
            description="Test",
            owner_agent=AgentRole.EXECUTOR,
            depends_on=[],
            acceptance_criteria=["OK"],
            status=TaskNodeStatus.PENDING,
        )],
        edges=[],
    )
    # Advance status directly to evidence_gate (skip EXECUTION state)
    task.update_status(TaskStatus.EVIDENCE_GATE)
    store.update_task(task)

    # Save an execution plan so apply_execution_plan doesn't reject
    store.save_execution_plan(
        task_id=task.task_id,
        plan_id="exec_plan_001",
        payload={"steps": [{"tool_name": "write_files", "input": {"paths": ["a.txt"], "contents": ["content"]}}]},
        idempotency_key="exec_plan_test",
    )

    # Save approval record so WriteGuard doesn't block
    store.create_approval(
        task_id=task.task_id,
        decision="approved",
        approved_by="admin",
        payload={"reason": "Test approval"},
        idempotency_key="approval_test",
    )

    # Return as dict (matching the API contract)
    return {"task_id": task.task_id, "status": task.status.value}


class TestProviderSelectedEvent:
    def test_dry_run_emits_provider_selected(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True})

        report = api.get_audit_report(t["task_id"])
        events = report["events"]
        provider_events = [e for e in events if e["event_type"] == "provider_selected"]
        assert len(provider_events) == 1
        assert provider_events[0]["provider"] == "fake"
        assert provider_events[0]["dry_run"] is True

    def test_real_provider_flag_checked(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True, "provider": "fake"})

        report = api.get_audit_report(t["task_id"])
        provider_events = [e for e in report["events"] if e["event_type"] == "provider_selected"]
        assert len(provider_events) == 1
        assert provider_events[0]["feature_flag_checked"] is False


class TestWriteGuardPassedEvent:
    def test_guard_pass_emits_write_guard_passed(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True})

        report = api.get_audit_report(t["task_id"])
        events = report["events"]
        guard_events = [e for e in events if e["event_type"] == "write_guard_passed"]
        assert len(guard_events) == 1
        assert guard_events[0]["risk_level"] == "low"
        assert guard_events[0]["operation_count"] >= 0


class TestWriteGuardBlockedEvent:
    def test_guard_block_emits_write_guard_blocked(self, api):
        t = _run_to_evidence_gate(api)
        with pytest.raises(PermissionError, match="branch_blocked"):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": True,
                "branch_name": "main",
            })

        report = api.get_audit_report(t["task_id"])
        events = report["events"]
        blocked_events = [e for e in events if e["event_type"] == "write_guard_blocked"]
        assert len(blocked_events) == 1
        assert blocked_events[0]["reason_code"] == "branch_blocked"
        assert blocked_events[0]["branch"] == "main"

    def test_blocked_no_provider_call(self, api):
        """Blocked → no branch_created/commit_created/pr_opened events."""
        t = _run_to_evidence_gate(api)
        with pytest.raises(PermissionError):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": True,
                "branch_name": "main",
            })

        report = api.get_audit_report(t["task_id"])
        event_types = [e["event_type"] for e in report["events"]]
        assert "branch_created" not in event_types
        assert "commit_created" not in event_types
        assert "pr_opened" not in event_types


class TestBranchCreatedEvent:
    def test_branch_created_emitted(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {
            "dry_run": True,
            "branch_name": "heart/test-p3e",
        })

        report = api.get_audit_report(t["task_id"])
        events = report["events"]
        branch_events = [e for e in events if e["event_type"] == "branch_created"]
        assert len(branch_events) == 1
        assert branch_events[0]["branch"] == "heart/test-p3e"
        assert branch_events[0]["base_branch"] == "main"


class TestCommitCreatedEvent:
    def test_commit_created_emitted(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {
            "dry_run": True,
            "branch_name": "heart/test-p3e",
        })

        report = api.get_audit_report(t["task_id"])
        events = report["events"]
        commit_events = [e for e in events if e["event_type"] == "commit_created"]
        assert len(commit_events) == 1
        assert commit_events[0]["file_count"] >= 0


class TestPROpenedEvent:
    def test_pr_opened_emitted(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {
            "dry_run": True,
            "branch_name": "heart/test-p3e",
        })

        report = api.get_audit_report(t["task_id"])
        events = report["events"]
        pr_events = [e for e in events if e["event_type"] == "pr_opened"]
        assert len(pr_events) == 1
        assert pr_events[0]["branch"] == "heart/test-p3e"
        assert pr_events[0]["pr_number"] >= 0


class TestEventSequence:
    def test_events_in_correct_order(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True})

        report = api.get_audit_report(t["task_id"])
        event_types = [e["event_type"] for e in report["events"]]
        # Expected order: provider_selected → write_guard_passed → branch_created → commit_created → pr_opened
        assert event_types.index("provider_selected") < event_types.index("write_guard_passed")
        assert event_types.index("write_guard_passed") < event_types.index("branch_created")
        assert event_types.index("branch_created") < event_types.index("commit_created")
        assert event_types.index("commit_created") < event_types.index("pr_opened")


class TestAuditReportStatus:
    def test_passed_status(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True})

        report = api.get_audit_report(t["task_id"])
        assert report["status"] == "passed"

    def test_blocked_status(self, api):
        t = _run_to_evidence_gate(api)
        with pytest.raises(PermissionError):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": True,
                "branch_name": "main",
            })

        report = api.get_audit_report(t["task_id"])
        assert report["status"] == "blocked"


class TestTaskStatusUnchanged:
    def test_apply_execution_plan_does_not_change_status(self, api):
        """P3-E constraint: apply_execution_plan() does not change task status."""
        t = _run_to_evidence_gate(api)
        assert t["status"] == TaskStatus.EVIDENCE_GATE.value

        api.apply_execution_plan(t["task_id"], {"dry_run": True})
        task = api.get_task(t["task_id"])
        assert task["status"] == TaskStatus.EVIDENCE_GATE.value

    def test_get_audit_report_does_not_change_status(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True})
        assert t["status"] == TaskStatus.EVIDENCE_GATE.value

        api.get_audit_report(t["task_id"])
        task = api.get_task(t["task_id"])
        assert task["status"] == TaskStatus.EVIDENCE_GATE.value

    def test_blocked_preserves_status(self, api):
        t = _run_to_evidence_gate(api)
        assert t["status"] == TaskStatus.EVIDENCE_GATE.value

        with pytest.raises(PermissionError):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": True,
                "branch_name": "main",
            })

        task = api.get_task(t["task_id"])
        assert task["status"] == TaskStatus.EVIDENCE_GATE.value


class TestIdempotency:
    def test_second_apply_same_events(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True})

        # Second call should be idempotent
        api.apply_execution_plan(t["task_id"], {"dry_run": True})

        report = api.get_audit_report(t["task_id"])
        # Only one set of events (second call is idempotent by task_id)
        provider_events = [e for e in report["events"] if e["event_type"] == "provider_selected"]
        assert len(provider_events) == 1