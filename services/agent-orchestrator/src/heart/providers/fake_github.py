"""FakeGitHubAdapter — in-memory Git provider for testing and dry-run.

No real GitHub API calls. All state is ephemeral (not persisted across
process restarts). For recovery tests, use a real store-backed adapter.
"""

from __future__ import annotations

import uuid
from typing import Any

from .git_provider import GitAdapter, GitOpResult, FileChange


class FakeGitHubAdapter(GitAdapter):
    """In-memory fake Git provider.

    Simulates: create_branch, commit_files, open_pr, get_commit_status
    Always succeeds in fake mode. Does not call any real API.

    State is ephemeral — lost on process restart.
    """

    def __init__(self) -> None:
        self._branches: dict[str, dict[str, Any]] = {}
        self._commits: dict[str, list[dict[str, Any]]] = {}
        self._prs: dict[str, dict[str, Any]] = {}

    def create_branch(self, branch: str, base: str = "main") -> GitOpResult:
        if branch in self._branches:
            return GitOpResult(
                success=True,
                operation="create_branch",
                data={
                    "branch": branch,
                    "base": base,
                    "already_exists": True,
                    "commit_sha": self._branches[branch].get("head_sha", ""),
                },
            )
        self._branches[branch] = {
            "name": branch,
            "base": base,
            "created_at": self._now_iso(),
            "head_sha": f"fake_sha_{branch}",
        }
        return GitOpResult(
            success=True,
            operation="create_branch",
            data={
                "branch": branch,
                "base": base,
                "already_exists": False,
                "commit_sha": self._branches[branch]["head_sha"],
            },
        )

    def commit_files(
        self,
        branch: str,
        changes: list[FileChange],
        message: str | None = None,
    ) -> GitOpResult:
        if branch not in self._branches:
            # auto-create branch if missing
            self.create_branch(branch)

        self._commits.setdefault(branch, [])
        commit = {
            "sha": f"fake_commit_{uuid.uuid4().hex[:12]}",
            "message": message or "Heart Mode execution plan update",
            "files": [c.path for c in changes],
            "timestamp": self._now_iso(),
        }
        self._commits[branch].append(commit)
        self._branches[branch]["head_sha"] = commit["sha"]

        return GitOpResult(
            success=True,
            operation="commit_files",
            data={
                "branch": branch,
                "commit_sha": commit["sha"],
                "file_count": len(changes),
                "files": [c.path for c in changes],
            },
        )

    def open_pr(
        self,
        branch: str,
        title: str,
        body: str,
        base: str = "main",
    ) -> GitOpResult:
        if branch not in self._branches:
            self.create_branch(branch)

        pr_id = f"PR-{len(self._prs) + 1}"
        pr = {
            "number": len(self._prs) + 1,
            "title": title,
            "body": body,
            "head": branch,
            "base": base,
            "state": "open",
            "url": f"https://github.com/fake-org/fake-repo/pull/{pr_id}",
            "created_at": self._now_iso(),
        }
        self._prs[pr_id] = pr

        return GitOpResult(
            success=True,
            operation="open_pr",
            data={
                "pr_number": pr["number"],
                "title": title,
                "url": pr["url"],
                "state": "open",
            },
        )

    def get_commit_status(self, ref: str) -> GitOpResult:
        return GitOpResult(
            success=True,
            operation="get_commit_status",
            data={
                "ref": ref,
                "state": "success",
                "statuses": [],
            },
        )

    # ── helpers ───────────────────────────────────────────────────────────

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def list_branches(self) -> list[str]:
        return list(self._branches.keys())

    def list_prs(self) -> list[dict[str, Any]]:
        return list(self._prs.values())

    def get_branch(self, branch: str) -> dict[str, Any] | None:
        return self._branches.get(branch)