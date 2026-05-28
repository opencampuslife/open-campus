"""Git provider interface and types.

P3-C scope: controlled write operations only.
Branch creation, file commit, PR open — no merge, no delete, no push-main.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class GitOpResult:
    """Result of a Git operation."""
    success: bool
    operation: str                     # "create_branch", "commit_files", "open_pr"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "operation": self.operation,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class FileChange:
    """A single file change in a commit."""
    path: str
    content: bytes
    message: str = "Heart Mode: update from execution plan"


# ── GitAdapter interface ──────────────────────────────────────────────────────

class GitAdapter(ABC):
    """Abstract interface for Git provider operations.

    P3-C allows: create_branch, commit_files, open_pr
    P3-C forbids: merge, push_main, delete_branch, delete_file, force_push
    """

    @abstractmethod
    def create_branch(self, branch: str, base: str = "main") -> GitOpResult:
        """Create a new branch from base. Returns branch info."""
        ...

    @abstractmethod
    def commit_files(
        self,
        branch: str,
        changes: list[FileChange],
        message: str | None = None,
    ) -> GitOpResult:
        """Commit one or more file changes to a branch. Returns commit info."""
        ...

    @abstractmethod
    def open_pr(
        self,
        branch: str,
        title: str,
        body: str,
        base: str = "main",
    ) -> GitOpResult:
        """Open a pull request. Returns PR info."""
        ...

    @abstractmethod
    def get_commit_status(self, ref: str) -> GitOpResult:
        """Check commit status (pass/fail/pending). Returns status info."""
        ...