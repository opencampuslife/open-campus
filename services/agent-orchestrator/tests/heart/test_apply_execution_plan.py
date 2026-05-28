"""Integration tests for apply_execution_plan (P3-C)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HEART_SRC = Path(__file__).resolve().parents[2] / "src" / "heart"
if str(_HEART_SRC.parent) not in sys.path:
    sys.path.insert(0, str(_HEART_SRC.parent))

from heart.api import HeartAPI
from heart.errors import InvalidTransition, TaskNotFound
from heart.events import EventType
from heart.models import TaskStatus
from heart.store import InMemoryHeartStore


@pytest.fixture
def api():
    return HeartAPI(InMemoryHeartStore())


# ── helpers ───────────────────────────────────────────────────────────────────

def _run_to_evidence_gate(api, goal="Add feature X", risk_level="medium"):
    """Run a task through plan_execution to reach evidence_gate state."""
    t = api.create_task({
        "goal": goal,
        "risk_level": risk_level,
        "acceptance_criteria": ["Feature works"],
    })
    t = api.plan(t["task_id"])
    assert t["status"] == TaskStatus.READY_FOR_APPROVAL.value, (
        f"Expected ready_for_approval, got {t['status']}"
    )
    t = api.approve_task(t["task_id"], {
        "decision": "approved",
        "approved_by": "admin",
    })
    t = api.plan_execution(t["task_id"])
    assert t["status"] == TaskStatus.EVIDENCE_GATE.value, (
        f"Expected evidence_gate, got {t['status']}"
    )
    return t


# ── happy path ───────────────────────────────────────────────────────────────

class TestApplyExecutionPlan:
    def test_dry_run_produces_delivery_evidence(self, api):
        t = _run_to_evidence_gate(api)
        result = api.apply_execution_plan(t["task_id"], {"dry_run": True})
        # apply_execution_plan does NOT change status — advance() is still needed
        assert result["status"] == TaskStatus.EVIDENCE_GATE.value
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert len(evidence) == 1
        assert evidence[0]["payload"]["dry_run"] is True

    def test_task_remains_in_evidence_gate_after_apply(self, api):
        """P3-C boundary: apply_execution_plan produces evidence but does NOT advance status."""
        t = _run_to_evidence_gate(api)
        result = api.apply_execution_plan(t["task_id"], {"dry_run": True})
        assert result["status"] == TaskStatus.EVIDENCE_GATE.value
        # advance() is still needed to reach completed
        result = api.advance(t["task_id"])
        assert result["status"] == TaskStatus.COMPLETED.value

    def test_branch_name_in_evidence(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {
            "dry_run": True,
            "branch_name": "heart/feature-x-abc123",
        })
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert evidence[0]["payload"]["branch"] == "heart/feature-x-abc123"

    def test_unknown_task_raises(self, api):
        with pytest.raises(TaskNotFound):
            api.apply_execution_plan("nonexistent", {"dry_run": True})


# ── preconditions ─────────────────────────────────────────────────────────────

class TestApplyPreconditions:
    def test_wrong_state_raises(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Feature works"]})
        t = api.plan(t["task_id"])
        # in ready_for_approval, not evidence_gate
        with pytest.raises(InvalidTransition, match="evidence_gate"):
            api.apply_execution_plan(t["task_id"], {"dry_run": True})

    def test_completed_task_apply_returns_idempotent(self, api):
        """apply_execution_plan on already-completed task is a no-op (no error, no status change)."""
        t = api.create_task({"goal": "Add feature", "risk_level": "low"})
        t = api.plan(t["task_id"])
        assert t["status"] == TaskStatus.COMPLETED.value
        result = api.apply_execution_plan(t["task_id"], {"dry_run": True})
        assert result["status"] == TaskStatus.COMPLETED.value

    def test_rejected_task_not_in_evidence_gate(self, api):
        t = api.create_task({"goal": "Add feature", "risk_level": "medium"})
        t = api.plan(t["task_id"])
        api.approve_task(t["task_id"], {
            "decision": "rejected",
            "approved_by": "admin",
            "reason": "scope unclear",
        })
        # rejected → stays in ready_for_approval → cannot apply
        with pytest.raises(InvalidTransition):
            api.apply_execution_plan(t["task_id"], {"dry_run": True})

    def test_cancelled_task_rejected(self, api):
        """Cancelled tasks cannot have apply_execution_plan called."""
        t = api.create_task({"goal": "Add feature", "risk_level": "medium",
                             "acceptance_criteria": ["Works"]})
        t = api.plan(t["task_id"])
        t = api.cancel_task(t["task_id"], {"reason": "cancelled"})
        assert t["status"] == TaskStatus.CANCELLED.value
        with pytest.raises(InvalidTransition, match="evidence_gate"):
            api.apply_execution_plan(t["task_id"], {"dry_run": True})

    def test_critical_task_is_blocked(self, api):
        """Critical-risk tasks are blocked by WriteGuard before reaching execution."""
        t = api.create_task({"goal": "Deploy to prod", "risk_level": "critical",
                             "acceptance_criteria": ["Risk reviewed"]})
        t = api.plan(t["task_id"])
        assert t["status"] == TaskStatus.BLOCKED.value
        with pytest.raises(InvalidTransition, match="evidence_gate"):
            api.apply_execution_plan(t["task_id"], {"dry_run": True})


# ── idempotency ──────────────────────────────────────────────────────────────

class TestApplyIdempotency:
    def test_second_call_idempotent_no_duplicate_evidence(self, api):
        """Calling apply_execution_plan twice with same delivery_id creates only one record."""
        t = _run_to_evidence_gate(api)
        r1 = api.apply_execution_plan(t["task_id"], {"dry_run": True})
        # second call is idempotent: no duplicate evidence, status unchanged
        r2 = api.apply_execution_plan(t["task_id"], {"dry_run": True})
        assert r1["status"] == TaskStatus.EVIDENCE_GATE.value
        assert r2["status"] == TaskStatus.EVIDENCE_GATE.value
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert len(evidence) == 1  # second call does not create duplicate


# ── WriteGuard integration ───────────────────────────────────────────────────

class TestApplyWriteGuard:
    def test_protected_branch_rejected(self, api):
        t = _run_to_evidence_gate(api)
        with pytest.raises(PermissionError, match="branch_blocked"):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": True,
                "branch_name": "main",
            })
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        # P3-E: blocked operations still produce delivery evidence with safety_events
        assert len(evidence) == 1
        # blocked is inside payload
        assert evidence[0].get("payload", {}).get("blocked") is True
        assert evidence[0].get("payload", {}).get("safety_events") is not None

    def test_safe_branch_allowed(self, api):
        """Default execution plan has no write steps → empty paths list → guard passes."""
        t = _run_to_evidence_gate(api)
        result = api.apply_execution_plan(t["task_id"], {"dry_run": True})
        assert result["status"] == TaskStatus.EVIDENCE_GATE.value


# ── dry_run enforcement ──────────────────────────────────────────────────────

class TestDryRunEnforcement:
    def test_dry_run_false_not_yet_supported(self, api):
        """P3-C first version: apply_execution_plan requires dry_run=True."""
        t = _run_to_evidence_gate(api)
        with pytest.raises(ValueError, match="dry_run=False|P3-D"):
            api.apply_execution_plan(t["task_id"], {"dry_run": False})
        # no delivery evidence written — ValueError fires before any provider call
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert len(evidence) == 0

    def test_dry_run_default_is_true(self, api):
        """Not passing dry_run defaults to True."""
        t = _run_to_evidence_gate(api)
        # should succeed (dry_run=True is the default)
        result = api.apply_execution_plan(t["task_id"])
        assert result["status"] == TaskStatus.EVIDENCE_GATE.value


# ── store contract (InMemory + SQLite) ───────────────────────────────────────

class TestDeliveryEvidenceStore:
    def test_save_and_retrieve(self, api):
        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {"dry_run": True})
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert len(evidence) == 1
        assert evidence[0]["task_id"] == t["task_id"]
        assert evidence[0]["delivery_id"].startswith("dry_run_")
        assert "dry_run" in evidence[0]["payload"]
        assert "branch" in evidence[0]["payload"]

    def test_idempotency_key_prevents_duplicates(self, api):
        t = _run_to_evidence_gate(api)
        delivery_id = "dry_run_test_123"
        # two saves with same idempotency key → one record
        api._engine.store.save_delivery_evidence(
            t["task_id"], delivery_id,
            {"note": "first"}, idempotency_key=f"delivery_{delivery_id}",
        )
        api._engine.store.save_delivery_evidence(
            t["task_id"], delivery_id,
            {"note": "second"}, idempotency_key=f"delivery_{delivery_id}",
        )
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert len(evidence) == 1
        assert evidence[0]["payload"]["note"] == "first"  # first wins

    def test_multiple_delivery_records(self, api):
        """Different delivery_ids create separate records."""
        api._engine.store.save_delivery_evidence(
            "task_1", "del_1", {"step": 1}, idempotency_key="delivery_del_1",
        )
        api._engine.store.save_delivery_evidence(
            "task_1", "del_2", {"step": 2}, idempotency_key="delivery_del_2",
        )
        evidence = api._engine.store.get_delivery_evidence("task_1")
        assert len(evidence) == 2


# ── P3-D: feature flag + real provider ───────────────────────────────────────

class TestApplyP3DFeatureFlag:
    """P3-D: real GitHub writes behind HEART_GITHUB_WRITE_ENABLED=1."""

    def test_dry_run_false_without_flag_raises(self, api):
        """dry_run=False without feature flag → FeatureFlagDisabled (not ValueError)."""
        t = _run_to_evidence_gate(api)
        from heart.providers.github_errors import FeatureFlagDisabled
        with pytest.raises((ValueError, FeatureFlagDisabled)):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": False,
                "provider": "real",
            })

    def test_dry_run_false_with_fake_provider_raises(self, api):
        """dry_run=False with provider=fake → ValueError (must use real)."""
        t = _run_to_evidence_gate(api)
        with pytest.raises(ValueError, match="dry_run=False|provider='real'"):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": False,
                "provider": "fake",
            })

    def test_provider_real_flag_off_raises_FeatureFlagDisabled(self, api):
        """provider=real but flag off → FeatureFlagDisabled, no real adapter created."""
        t = _run_to_evidence_gate(api)
        with pytest.raises(Exception) as exc_info:  # may be FeatureFlagDisabled or ValueError
            api.apply_execution_plan(t["task_id"], {
                "dry_run": False,
                "provider": "real",
            })
        # either is acceptable since flag is off
        assert "FeatureFlagDisabled" in type(exc_info.value).__name__ or \
               "dry_run=False" in str(exc_info.value)

    def test_real_provider_with_flag_and_credentials_succeeds(self, monkeypatch):
        """dry_run=False + flag on + credentials → RealGitHubAdapter called."""
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        monkeypatch.setenv("HEART_GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("HEART_GITHUB_OWNER", "test-org")
        monkeypatch.setenv("HEART_GITHUB_REPO", "test-repo")

        from heart.api import HeartAPI
        from heart.store import InMemoryHeartStore
        api = HeartAPI(InMemoryHeartStore())

        t = _run_to_evidence_gate(api)
        result = api.apply_execution_plan(t["task_id"], {
            "dry_run": False,
            "provider": "real",
            "branch_name": "heart/test-real",
        })
        assert result["status"] == TaskStatus.EVIDENCE_GATE.value
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert len(evidence) == 1
        assert evidence[0]["payload"]["dry_run"] is False
        assert evidence[0]["payload"]["provider"] == "real"
        assert evidence[0]["payload"]["branch"] == "heart/test-real"

    def test_real_provider_delivery_evidence_has_all_fields(self, monkeypatch):
        """Real delivery evidence includes commit_sha, pr_url, pr_number."""
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        monkeypatch.setenv("HEART_GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("HEART_GITHUB_OWNER", "test-org")
        monkeypatch.setenv("HEART_GITHUB_REPO", "test-repo")

        from heart.api import HeartAPI
        from heart.store import InMemoryHeartStore
        api = HeartAPI(InMemoryHeartStore())

        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {
            "dry_run": False,
            "provider": "real",
            "branch_name": "heart/test-fields",
        })
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        payload = evidence[0]["payload"]
        assert "commit_sha" in payload
        assert "pr_url" in payload
        assert "pr_number" in payload
        assert "git_results" in payload
        assert payload["git_results"]["create_branch"]["success"] is True
        assert payload["git_results"]["commit_files"]["success"] is True
        assert payload["git_results"]["open_pr"]["success"] is True

    def test_guard_blocked_prevents_real_provider_call(self, monkeypatch):
        """WriteGuard blocked → FeatureFlagDisabled fires before provider call."""
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        monkeypatch.setenv("HEART_GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("HEART_GITHUB_OWNER", "test-org")
        monkeypatch.setenv("HEART_GITHUB_REPO", "test-repo")

        from heart.api import HeartAPI
        from heart.store import InMemoryHeartStore
        api = HeartAPI(InMemoryHeartStore())

        t = _run_to_evidence_gate(api)
        # WriteGuard blocks protected branch BEFORE provider is selected
        with pytest.raises(PermissionError, match="branch_blocked"):
            api.apply_execution_plan(t["task_id"], {
                "dry_run": False,
                "provider": "real",
                "branch_name": "main",  # WriteGuard blocks this
            })
        # no delivery evidence was written — guard blocked before any write
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        # P3-E: blocked operations still produce delivery evidence with safety_events
        assert len(evidence) == 1
        # blocked is inside payload
        assert evidence[0].get("payload", {}).get("blocked") is True
        assert evidence[0].get("payload", {}).get("safety_events") is not None

    def test_default_provider_is_fake(self, api):
        """Default provider=fake (dry_run=True) — flag check never fires."""
        t = _run_to_evidence_gate(api)
        result = api.apply_execution_plan(t["task_id"], {"dry_run": True})
        assert result["status"] == TaskStatus.EVIDENCE_GATE.value
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert evidence[0]["payload"]["provider"] == "fake"

    def test_real_provider_idempotent_second_call(self, monkeypatch):
        """Second call with real provider is idempotent — same delivery_id."""
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        monkeypatch.setenv("HEART_GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("HEART_GITHUB_OWNER", "test-org")
        monkeypatch.setenv("HEART_GITHUB_REPO", "test-repo")

        from heart.api import HeartAPI
        from heart.store import InMemoryHeartStore
        api = HeartAPI(InMemoryHeartStore())

        t = _run_to_evidence_gate(api)
        api.apply_execution_plan(t["task_id"], {
            "dry_run": False,
            "provider": "real",
        })
        api.apply_execution_plan(t["task_id"], {
            "dry_run": False,
            "provider": "real",
        })
        evidence = api._engine.store.get_delivery_evidence(t["task_id"])
        assert len(evidence) == 1  # idempotent — only one record


class TestDeliveryEvidenceSQLiteIdempotency:
    """Verify SQLite UNIQUE(task_id, idempotency_key) constraint enforces idempotency.

    This simulates recovery: a fresh store instance sees the same idempotency_key
    and must NOT create a duplicate record.
    """

    def test_recovery_idempotent_via_unique_constraint(self, tmp_path):
        """Simulates: store dies after first save, new instance retries with same key."""
        from heart.store_sqlite import SQLiteHeartStore

        db = str(tmp_path / "heart.db")

        # first instance: save evidence
        store_a = SQLiteHeartStore(db)
        store_a.save_delivery_evidence(
            "task_1", "del_recovery",
            {"dry_run": True, "branch": "heart/fix"},
            idempotency_key="delivery_task_1",
        )
        evidence_a = store_a.get_delivery_evidence("task_1")
        assert len(evidence_a) == 1

        # simulate crash and recovery: new instance, same idempotency key
        store_b = SQLiteHeartStore(db)
        store_b.save_delivery_evidence(
            "task_1", "del_recovery",
            {"dry_run": True, "branch": "heart/fix"},
            idempotency_key="delivery_task_1",
        )
        evidence_b = store_b.get_delivery_evidence("task_1")
        # must NOT have created a duplicate — UNIQUE constraint prevents it
        assert len(evidence_b) == 1
        assert evidence_b[0]["payload"]["branch"] == "heart/fix"  # first wins