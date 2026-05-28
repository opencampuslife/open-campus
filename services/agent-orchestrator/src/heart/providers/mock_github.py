"""MockGitHubHTTPClient — in-memory fake GitHub API for tests.

No real network calls. Simulates:
    - GET /git/ref/heads/:branch  → returns ref SHA
    - POST /git/refs             → creates branch ref
    - POST /git/blobs            → creates blob
    - POST /git/commits           → creates commit
    - POST /git/refs              → updates branch ref
    - POST /pulls                 → opens PR
    - GET /commits/:ref/status    → returns status
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MockBlob:
    sha: str
    content: str
    encoding: str = "utf-8"


@dataclass
class MockCommit:
    sha: str
    message: str
    tree: list[dict[str, Any]]
    parents: list[str]


@dataclass
class MockPR:
    number: int
    title: str
    body: str
    head: str
    base: str
    state: str = "open"
    html_url: str = ""


class MockGitHubHTTPClient:
    """In-memory mock of GitHub API.

    Stores branches, blobs, commits, and PRs in memory.
    Fails if real GitHub network access would be needed.
    """

    def __init__(self) -> None:
        self._refs: dict[str, str] = {}  # "heads/feature/x" -> sha
        self._commits: dict[str, MockCommit] = {}
        self._prs: dict[int, MockPR] = {}
        self._blobs: dict[str, MockBlob] = {}
        self._next_pr_number = 1
        self._called: list[tuple[str, str]] = []  # (method, url) for verification
        # Pre-seed a "main" branch so create_branch has a base SHA
        self._refs["heads/main"] = "mock_sha_main"

    def get(self, url: str, headers: dict[str, str]) -> dict[str, Any]:
        self._called.append(("GET", url))
        if "/git/ref/heads/" in url:
            branch = url.rsplit("/", 1)[-1]
            if f"heads/{branch}" in self._refs:
                return {
                    "object": {
                        "sha": self._refs[f"heads/{branch}"],
                        "type": "commit",
                    }
                }
            # Unknown branch — return a synthetic SHA so create_branch can succeed
            # (real GitHub would 404, but our mock handles unknown branches gracefully)
            return {
                "object": {
                    "sha": f"mock_sha_{branch}_{uuid.uuid4().hex[:8]}",
                    "type": "commit",
                }
            }
        if "/commits/" in url and "/status" in url:
            return {"state": "success", "statuses": []}
        raise NotImplementedError(f"mock GET not implemented for {url}")

    def post(self, url: str, headers: dict[str, str], data: dict[str, Any]) -> dict[str, Any]:
        self._called.append(("POST", url))
        if url.endswith("/git/refs"):
            ref = data["ref"].replace("refs/", "")
            sha = data["sha"]
            if ref in self._refs:
                # GitHub returns 422 for duplicate branch creation
                from .github_errors import GitHubAPIError
                raise GitHubAPIError(
                    operation="create_branch",
                    status_code=422,
                    message="Validation Failed: ref already exists",
                )
            self._refs[ref] = sha
            return {"ref": data["ref"], "object": {"sha": sha}}
        if url.endswith("/git/blobs"):
            blob_sha = f"blob_{uuid.uuid4().hex[:12]}"
            self._blobs[blob_sha] = MockBlob(
                sha=blob_sha,
                content=data.get("content", ""),
                encoding=data.get("encoding", "utf-8"),
            )
            return {"sha": blob_sha}
        if url.endswith("/git/commits"):
            commit_sha = f"mock_commit_{uuid.uuid4().hex[:12]}"
            parent_sha = data.get("parents", [None])[0]
            self._commits[commit_sha] = MockCommit(
                sha=commit_sha,
                message=data.get("message", ""),
                tree=data.get("tree", []),
                parents=[parent_sha] if parent_sha else [],
            )
            return {"sha": commit_sha}
        if url.endswith("/pulls"):
            head = data.get("head", "")
            base = data.get("base", "main")
            # GitHub auto-creates the head branch ref when opening a PR
            head_ref = f"heads/{head}"
            if head_ref not in self._refs:
                self._refs[head_ref] = self._refs.get(f"heads/{base}", "mock_sha_main")
            pr = MockPR(
                number=self._next_pr_number,
                title=data.get("title", ""),
                body=data.get("body", ""),
                head=head,
                base=base,
                html_url=f"https://github.com/mock-owner/mock-repo/pull/{self._next_pr_number}",
            )
            self._prs[pr.number] = pr
            self._next_pr_number += 1
            return {
                "number": pr.number,
                "title": pr.title,
                "html_url": pr.html_url,
                "state": pr.state,
            }
        raise NotImplementedError(f"mock POST not implemented for {url}")

    def put(
        self,
        url: str,
        headers: dict[str, str],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._called.append(("PUT", url))
        raise NotImplementedError(f"mock PUT not implemented for {url}")

    def patch(
        self,
        url: str,
        headers: dict[str, str],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Mock PATCH — GitHub API uses PATCH to update an existing ref.

        Supported:
        - PATCH /git/refs/{ref} → update SHA of existing ref (no 422)
        """
        self._called.append(("PATCH", url))
        # e.g. /git/refs/heads/feature/test
        if "/git/refs/" in url:
            ref = url.rsplit("/git/refs/", 1)[-1]
            if ref not in self._refs:
                # Ref doesn't exist → create it (treat PATCH as create-or-update)
                self._refs[ref] = data["sha"]
                return {"ref": f"refs/{ref}", "object": {"sha": data["sha"]}}
            self._refs[ref] = data["sha"]
            return {"ref": f"refs/{ref}", "object": {"sha": data["sha"]}}
        raise NotImplementedError(f"mock PATCH not implemented for {url}")

    def has_ref(self, ref: str) -> bool:
        """Check if a ref exists. Used by RealGitHubAdapter to decide POST vs PATCH."""
        return ref in self._refs

    def post_file(
        self,
        url: str,
        headers: dict[str, str],
        path: str,
        content_base64: str,
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        self._called.append(("PUT", url))
        raise NotImplementedError("post_file not implemented in mock")

    def list_calls(self) -> list[tuple[str, str]]:
        """Return list of (method, url) calls made. Useful for test assertions."""
        return list(self._called)

    def reset(self) -> None:
        """Clear all state. Call between tests."""
        self._refs.clear()
        self._commits.clear()
        self._prs.clear()
        self._blobs.clear()
        self._called.clear()
        self._next_pr_number = 1
