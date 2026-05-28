"""Tests for RealGitHubAdapter with mocked HTTP client (P3-D)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HEART_SRC = Path(__file__).resolve().parents[2] / "src" / "heart"
if str(_HEART_SRC.parent) not in sys.path:
    sys.path.insert(0, str(_HEART_SRC.parent))

from heart.providers import (
    FileChange,
    GitHubProviderConfig,
    MockGitHubHTTPClient,
    RealGitHubAdapter,
)


@pytest.fixture
def config():
    return GitHubProviderConfig(
        github_write_enabled=True,
        provider="real",
        github_token="ghp_test",
        github_owner="test-org",
        github_repo="test-repo",
        github_api_url="https://api.github.com",
    )


@pytest.fixture
def mock_client():
    return MockGitHubHTTPClient()


@pytest.fixture
def real_adapter(config, mock_client):
    return RealGitHubAdapter(config, http_client=mock_client)


# ── create_branch ─────────────────────────────────────────────────────────────

class TestCreateBranch:
    def test_creates_branch(self, real_adapter, mock_client):
        result = real_adapter.create_branch("feature/test")
        assert result.success is True
        assert result.operation == "create_branch"
        assert result.data["branch"] == "feature/test"
        assert result.data["already_exists"] is False
        assert "commit_sha" in result.data

    def test_duplicate_branch_returns_existing(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/test")
        result = real_adapter.create_branch("feature/test")
        assert result.success is True
        assert result.data["already_exists"] is True
        # branch stored with heads/ prefix
        assert "heads/feature/test" in mock_client._refs

    def test_calls_github_api(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/api-call")
        calls = mock_client.list_calls()
        get_calls = [(m, u) for m, u in calls if m == "GET"]
        post_calls = [(m, u) for m, u in calls if m == "POST"]
        assert any("git/ref/heads/main" in u for m, u in get_calls)
        assert any("git/refs" in u for m, u in post_calls)


# ── commit_files ─────────────────────────────────────────────────────────────

class TestCommitFiles:
    def test_commits_single_file(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/test")
        changes = [FileChange(path="README.md", content=b"# Test")]
        result = real_adapter.commit_files("feature/test", changes)
        assert result.success is True
        assert result.operation == "commit_files"
        assert result.data["file_count"] == 1
        assert "commit_sha" in result.data

    def test_commits_multiple_files(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/test")
        changes = [
            FileChange(path="src/a.py", content=b"print('a')"),
            FileChange(path="src/b.py", content=b"x = 1"),
        ]
        result = real_adapter.commit_files("feature/test", changes)
        assert result.success is True
        assert result.data["file_count"] == 2

    def test_auto_creates_branch(self, real_adapter, mock_client):
        # don't call create_branch first
        result = real_adapter.commit_files("feature/new", [
            FileChange(path="README.md", content=b"# New"),
        ])
        assert result.success is True
        assert "heads/feature/new" in mock_client._refs

    def test_creates_blobs_and_commits(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/test")
        real_adapter.commit_files("feature/test", [
            FileChange(path="a.txt", content=b"content"),
        ])
        calls = mock_client.list_calls()
        post_calls = [u for m, u in calls if m == "POST"]
        # blob creation
        assert any("git/blobs" in u for u in post_calls)
        # commit creation
        assert any("git/commits" in u for u in post_calls)


# ── open_pr ─────────────────────────────────────────────────────────────────

class TestOpenPR:
    def test_opens_pr(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/test")
        result = real_adapter.open_pr("feature/test", "Add feature", "Description")
        assert result.success is True
        assert result.operation == "open_pr"
        assert result.data["state"] == "open"
        assert result.data["pr_number"] == 1
        assert "github.com" in result.data["url"]

    def test_multiple_prs_increment_number(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/a")
        real_adapter.create_branch("feature/b")
        pr_a = real_adapter.open_pr("feature/a", "PR A", "")
        pr_b = real_adapter.open_pr("feature/b", "PR B", "")
        assert pr_a.data["pr_number"] != pr_b.data["pr_number"]

    def test_auto_creates_branch_for_pr(self, real_adapter, mock_client):
        result = real_adapter.open_pr("feature/new", "Title", "Body")
        assert result.success is True
        assert "heads/feature/new" in mock_client._refs


# ── get_commit_status ────────────────────────────────────────────────────────

class TestGetCommitStatus:
    def test_returns_success_status(self, real_adapter, mock_client):
        result = real_adapter.get_commit_status("abc123")
        assert result.success is True
        assert result.operation == "get_commit_status"
        assert result.data["state"] == "success"
        assert result.data["ref"] == "abc123"


# ── state isolation ──────────────────────────────────────────────────────────

class TestStateIsolation:
    def test_different_branches_independent(self, real_adapter, mock_client):
        real_adapter.create_branch("feature/a")
        real_adapter.create_branch("feature/b")
        real_adapter.commit_files("feature/a", [FileChange(path="a.txt", content=b"a")])
        real_adapter.commit_files("feature/b", [FileChange(path="b.txt", content=b"b")])
        sha_a = mock_client._refs.get("heads/feature/a", "")
        sha_b = mock_client._refs.get("heads/feature/b", "")
        assert sha_a != sha_b

    def test_reset_clears_all_state(self, mock_client):
        mock_client._refs["heads/test"] = "sha123"
        mock_client._prs[1] = {"number": 1}
        mock_client.reset()
        assert len(mock_client._refs) == 0
        assert len(mock_client._prs) == 0
        assert len(mock_client._called) == 0
        assert mock_client._next_pr_number == 1
