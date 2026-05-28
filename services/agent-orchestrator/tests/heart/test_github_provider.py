"""Unit tests for FakeGitHubAdapter (in-memory git provider)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HEART_SRC = Path(__file__).resolve().parents[2] / "src" / "heart"
if str(_HEART_SRC.parent) not in sys.path:
    sys.path.insert(0, str(_HEART_SRC.parent))

from heart.providers import FakeGitHubAdapter, FileChange


@pytest.fixture
def git():
    return FakeGitHubAdapter()


# ── create_branch ─────────────────────────────────────────────────────────────

class TestCreateBranch:
    def test_creates_branch(self, git):
        result = git.create_branch("feature/test")
        assert result.success
        assert result.operation == "create_branch"
        assert result.data["branch"] == "feature/test"
        assert not result.data["already_exists"]

    def test_duplicate_branch_returns_existing(self, git):
        git.create_branch("feature/test")
        result = git.create_branch("feature/test")
        assert result.success
        assert result.data["already_exists"]

    def test_branch_with_base(self, git):
        result = git.create_branch("feature/test", base="main")
        assert result.success
        assert result.data["base"] == "main"

    def test_branch_list(self, git):
        git.create_branch("feature/a")
        git.create_branch("feature/b")
        assert set(git.list_branches()) == {"feature/a", "feature/b"}


# ── commit_files ─────────────────────────────────────────────────────────────

class TestCommitFiles:
    def test_commits_to_new_branch(self, git):
        git.create_branch("feature/test")
        result = git.commit_files("feature/test", [])
        assert result.success
        assert result.operation == "commit_files"
        assert result.data["branch"] == "feature/test"
        assert result.data["commit_sha"].startswith("fake_commit_")

    def test_commits_multiple_files(self, git):
        git.create_branch("feature/test")
        changes = [
            FileChange(path="src/a.py", content=b"print('hello')"),
            FileChange(path="src/b.py", content=b"x = 1"),
        ]
        result = git.commit_files("feature/test", changes)
        assert result.success
        assert result.data["file_count"] == 2
        assert set(result.data["files"]) == {"src/a.py", "src/b.py"}

    def test_auto_creates_branch(self, git):
        # don't call create_branch first
        result = git.commit_files("feature/new", [
            FileChange(path="README.md", content=b"# Test"),
        ])
        assert result.success
        assert "feature/new" in git.list_branches()

    def test_commit_message_default(self, git):
        git.create_branch("feature/test")
        result = git.commit_files("feature/test", [])
        assert "Heart Mode" in git._commits["feature/test"][0]["message"]

    def test_commit_message_custom(self, git):
        git.create_branch("feature/test")
        result = git.commit_files("feature/test", [], message="my custom message")
        assert git._commits["feature/test"][0]["message"] == "my custom message"

    def test_multiple_commits(self, git):
        git.create_branch("feature/test")
        r1 = git.commit_files("feature/test", [])
        r2 = git.commit_files("feature/test", [])
        assert r1.data["commit_sha"] != r2.data["commit_sha"]
        assert len(git._commits["feature/test"]) == 2


# ── open_pr ───────────────────────────────────────────────────────────────────

class TestOpenPR:
    def test_opens_pr(self, git):
        git.create_branch("feature/test")
        result = git.open_pr("feature/test", "Add feature", "Description")
        assert result.success
        assert result.operation == "open_pr"
        assert result.data["state"] == "open"
        assert result.data["pr_number"] == 1
        assert "github.com" in result.data["url"]

    def test_pr_body_stored(self, git):
        git.create_branch("feature/test")
        git.open_pr("feature/test", "Add feature", "Body text")
        assert git._prs["PR-1"]["body"] == "Body text"

    def test_multiple_prs(self, git):
        git.create_branch("feature/a")
        git.create_branch("feature/b")
        git.open_pr("feature/a", "PR A", "")
        git.open_pr("feature/b", "PR B", "")
        assert len(git._prs) == 2
        assert {pr["head"] for pr in git.list_prs()} == {"feature/a", "feature/b"}

    def test_auto_creates_branch_for_pr(self, git):
        # don't call create_branch first
        result = git.open_pr("feature/new", "Title", "")
        assert result.success
        assert "feature/new" in git.list_branches()


# ── get_commit_status ────────────────────────────────────────────────────────

class TestGetCommitStatus:
    def test_returns_success(self, git):
        result = git.get_commit_status("abc123")
        assert result.success
        assert result.operation == "get_commit_status"
        assert result.data["state"] == "success"
        assert result.data["ref"] == "abc123"


# ── idempotency / state ──────────────────────────────────────────────────────

class TestIdempotency:
    def test_state_persists_in_memory(self, git):
        git.create_branch("feature/test")
        assert "feature/test" in git.list_branches()
        assert git.get_branch("feature/test") is not None

    def test_different_branches_independent(self, git):
        git.create_branch("feature/a")
        git.create_branch("feature/b")
        git.commit_files("feature/a", [FileChange(path="a.txt", content=b"a")])
        git.commit_files("feature/b", [FileChange(path="b.txt", content=b"b")])
        sha_a = git.get_branch("feature/a")["head_sha"]
        sha_b = git.get_branch("feature/b")["head_sha"]
        assert sha_a != sha_b

    def test_pr_state_isolated_per_branch(self, git):
        git.create_branch("feature/a")
        git.create_branch("feature/b")
        pr_a = git.open_pr("feature/a", "PR A", "")
        pr_b = git.open_pr("feature/b", "PR B", "")
        assert pr_a.data["pr_number"] != pr_b.data["pr_number"]