"""Unit tests for WriteGuard security gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HEART_SRC = Path(__file__).resolve().parents[2] / "src" / "heart"
if str(_HEART_SRC.parent) not in sys.path:
    sys.path.insert(0, str(_HEART_SRC.parent))

from heart.write_guard import WriteGuard, WriteGuardResult


@pytest.fixture
def guard():
    return WriteGuard()


# ── branch checks ───────────────────────────────────────────────────────────

class TestBranchChecks:
    def test_main_blocked(self, guard):
        result = guard.check_branch("main")
        assert not result.allowed
        assert result.code == "branch_blocked"

    def test_master_blocked(self, guard):
        result = guard.check_branch("master")
        assert not result.allowed

    def test_production_blocked(self, guard):
        result = guard.check_branch("production")
        assert not result.allowed

    def test_release_blocked(self, guard):
        result = guard.check_branch("release")
        assert not result.allowed

    def test_feature_branch_allowed(self, guard):
        result = guard.check_branch("feature/add-heart-mode")
        assert result.allowed

    def test_heart_prefix_allowed(self, guard):
        result = guard.check_branch("heart/my-task-abc123")
        assert result.allowed

    def test_main_prefix_blocked(self, guard):
        result = guard.check_branch("main/fix-typo")
        assert not result.allowed

    def test_empty_branch_allowed(self, guard):
        result = guard.check_branch("feature-branch")
        assert result.allowed


# ── path checks ──────────────────────────────────────────────────────────────

class TestPathChecks:
    def test_env_file_blocked(self, guard):
        result = guard.check_paths([".env"])
        assert not result.allowed
        assert result.code == "path_blocked"

    def test_env_local_blocked(self, guard):
        result = guard.check_paths(["config/.env.local"])
        assert not result.allowed

    def test_secrets_dir_blocked(self, guard):
        result = guard.check_paths(["secrets/prod.json"])
        assert not result.allowed

    def test_auth_config_blocked(self, guard):
        result = guard.check_paths(["src/auth/oauth.py"])
        assert not result.allowed

    def test_credentials_file_blocked(self, guard):
        result = guard.check_paths(["credentials.json"])
        assert not result.allowed

    def test_github_workflow_blocked(self, guard):
        result = guard.check_paths([".github/workflows/ci.yml"])
        assert not result.allowed

    def test_gitignore_blocked(self, guard):
        result = guard.check_paths([".gitignore"])
        assert not result.allowed

    def test_package_lock_blocked(self, guard):
        result = guard.check_paths(["package-lock.json"])
        assert not result.allowed

    def test_yarn_lock_blocked(self, guard):
        result = guard.check_paths(["yarn.lock"])
        assert not result.allowed

    def test_pem_key_blocked(self, guard):
        result = guard.check_paths(["keys/server.pem"])
        assert not result.allowed

    def test_safe_path_allowed(self, guard):
        result = guard.check_paths(["src/handlers/user.py", "README.md"])
        assert result.allowed

    def test_multiple_paths_one_blocked(self, guard):
        result = guard.check_paths(["src/good.py", ".env"])
        assert not result.allowed

    def test_empty_paths_allowed(self, guard):
        result = guard.check_paths([])
        assert result.allowed

    def test_deploy_dir_blocked(self, guard):
        result = guard.check_paths(["deploy/production.sh"])
        assert not result.allowed

    def test_terraform_blocked(self, guard):
        result = guard.check_paths(["infra/terraform/main.tf"])
        assert not result.allowed

    def test_sensitive_keyword_blocked(self, guard):
        result = guard.check_paths(["src/password.py"])
        assert not result.allowed


# ── operation checks ─────────────────────────────────────────────────────────

class TestOperationChecks:
    def test_merge_blocked(self, guard):
        result = guard.check_operation("merge")
        assert not result.allowed
        assert result.code == "op_blocked"

    def test_delete_branch_blocked(self, guard):
        result = guard.check_operation("delete_branch")
        assert not result.allowed

    def test_force_push_blocked(self, guard):
        result = guard.check_operation("force_push")
        assert not result.allowed

    def test_push_main_blocked(self, guard):
        result = guard.check_operation("push_main")
        assert not result.allowed

    def test_delete_file_blocked(self, guard):
        result = guard.check_operation("delete_file")
        assert not result.allowed

    def test_modify_secret_blocked(self, guard):
        result = guard.check_operation("modify_secret")
        assert not result.allowed

    def test_modify_auth_policy_blocked(self, guard):
        result = guard.check_operation("modify_auth_policy")
        assert not result.allowed

    def test_modify_deploy_config_blocked(self, guard):
        result = guard.check_operation("modify_deploy_config")
        assert not result.allowed

    def test_commit_files_allowed(self, guard):
        result = guard.check_operation("commit_files")
        assert result.allowed

    def test_create_branch_allowed(self, guard):
        result = guard.check_operation("create_branch")
        assert result.allowed

    def test_open_pr_allowed(self, guard):
        result = guard.check_operation("open_pr")
        assert result.allowed


# ── risk level checks ─────────────────────────────────────────────────────────

class TestRiskLevelChecks:
    def test_critical_always_blocked(self, guard):
        result = guard.check_risk_level("critical")
        assert not result.allowed
        assert result.code == "risk_blocked"

    def test_high_blocked(self, guard):
        result = guard.check_risk_level("high")
        assert not result.allowed

    def test_medium_allowed(self, guard):
        result = guard.check_risk_level("medium")
        assert result.allowed

    def test_low_allowed(self, guard):
        result = guard.check_risk_level("low")
        assert result.allowed


# ── approval checks ───────────────────────────────────────────────────────────

class TestApprovalChecks:
    def test_no_approval_blocked(self, guard):
        result = guard.check_approval(has_approval=False)
        assert not result.allowed
        assert result.code == "approval_required"

    def test_has_approval_allowed(self, guard):
        result = guard.check_approval(has_approval=True)
        assert result.allowed


# ── execution plan checks ─────────────────────────────────────────────────────

class TestPlanChecks:
    def test_no_plan_blocked(self, guard):
        result = guard.check_execution_plan(has_plan=False)
        assert not result.allowed
        assert result.code == "missing_plan"

    def test_has_plan_allowed(self, guard):
        result = guard.check_execution_plan(has_plan=True)
        assert result.allowed


# ── file size checks ─────────────────────────────────────────────────────────

class TestFileSizeChecks:
    def test_under_limit_allowed(self, guard):
        result = guard.check_file_size(b"x" * 1000)
        assert result.allowed

    def test_at_limit_allowed(self, guard):
        result = guard.check_file_size(b"x" * (512 * 1024))
        assert result.allowed

    def test_over_limit_blocked(self, guard):
        result = guard.check_file_size(b"x" * (512 * 1024 + 1))
        assert not result.allowed
        assert result.code == "size_blocked"


# ── check_all (cumulative) ────────────────────────────────────────────────────

class TestCheckAll:
    def test_all_pass(self, guard):
        result = guard.check_all(
            branch="feature/my-task",
            paths=["src/good.py"],
            operation="commit_files",
            content=b"hello",
            risk_level="medium",
            has_approval=True,
            has_plan=True,
        )
        assert result.allowed

    def test_first_failure_stops(self, guard):
        result = guard.check_all(
            branch="main",  # blocked
            paths=["src/good.py"],
            operation="commit_files",
            risk_level="medium",
            has_approval=True,
            has_plan=True,
        )
        assert not result.allowed
        assert result.code == "branch_blocked"

    def test_approval_fails(self, guard):
        result = guard.check_all(
            branch="feature/my-task",
            paths=["src/good.py"],
            operation="commit_files",
            risk_level="medium",
            has_approval=False,  # blocked
            has_plan=True,
        )
        assert not result.allowed
        assert result.code == "approval_required"

    def test_partial_checks_skip_none(self, guard):
        result = guard.check_all(
            branch="feature/my-task",
            paths=["src/good.py"],
            # operation=None → skipped
            # content=None → skipped
            risk_level="medium",
            has_approval=True,
            has_plan=True,
        )
        assert result.allowed


# ── WriteGuardResult helpers ─────────────────────────────────────────────────

class TestResultHelpers:
    def test_ok(self):
        result = WriteGuardResult.ok()
        assert result.allowed
        assert result.reason is None
        assert result.code is None

    def test_blocked(self):
        result = WriteGuardResult.blocked("forbidden", "branch_blocked")
        assert not result.allowed
        assert result.reason == "forbidden"
        assert result.code == "branch_blocked"