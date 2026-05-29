"""Safety event protocol — normalized audit events for Git provider writes.

P3-E scope: defines the 6 event types and their required fields.
No execution, no state changes, no new tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── Event type enumeration ──────────────────────────────────────────────────

class SafetyEventType(Enum):
    """Normalized safety event types for provider write audit.

    All events are read-only audit records. They do not change TaskStatus.
    """
    PROVIDER_SELECTED = "provider_selected"
    WRITE_GUARD_PASSED = "write_guard_passed"
    WRITE_GUARD_BLOCKED = "write_guard_blocked"
    BRANCH_CREATED = "branch_created"
    COMMIT_CREATED = "commit_created"
    PR_OPENED = "pr_opened"


# ── Core event dataclass ────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SafetyEvent:
    """A single normalized safety audit event.

    Immutable. All events share the same top-level envelope with:
    - event_type: the normalized event name
    - timestamp: ISO-8601 UTC
    - provider: which git provider was used ("fake" | "real")
    - dry_run: whether this was a dry run
    - metadata: free-form extra context
    """
    event_type: SafetyEventType
    timestamp: str
    provider: str
    dry_run: bool
    # Per-event required fields
    branch: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    file_count: int | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    title: str | None = None
    repo: str | None = None
    reason_code: str | None = None
    blocked_paths: list[str] | None = None
    blocked_operations: list[str] | None = None
    operation_count: int | None = None
    risk_level: str | None = None
    feature_flag_checked: bool = False
    feature_flag_enabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON storage."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "provider": self.provider,
            "dry_run": self.dry_run,
            "branch": self.branch,
            "base_branch": self.base_branch,
            "commit_sha": self.commit_sha,
            "file_count": self.file_count,
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "title": self.title,
            "repo": self.repo,
            "reason_code": self.reason_code,
            "blocked_paths": self.blocked_paths,
            "blocked_operations": self.blocked_operations,
            "operation_count": self.operation_count,
            "risk_level": self.risk_level,
            "feature_flag_checked": self.feature_flag_checked,
            "feature_flag_enabled": self.feature_flag_enabled,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyEvent:
        """Deserialize from a plain dict."""
        event_type = SafetyEventType(data["event_type"])
        return cls(
            event_type=event_type,
            timestamp=data["timestamp"],
            provider=data["provider"],
            dry_run=data["dry_run"],
            branch=data.get("branch"),
            base_branch=data.get("base_branch"),
            commit_sha=data.get("commit_sha"),
            file_count=data.get("file_count"),
            pr_number=data.get("pr_number"),
            pr_url=data.get("pr_url"),
            title=data.get("title"),
            repo=data.get("repo"),
            reason_code=data.get("reason_code"),
            blocked_paths=data.get("blocked_paths"),
            blocked_operations=data.get("blocked_operations"),
            operation_count=data.get("operation_count"),
            risk_level=data.get("risk_level"),
            feature_flag_checked=data.get("feature_flag_checked", False),
            feature_flag_enabled=data.get("feature_flag_enabled", False),
            metadata=data.get("metadata", {}),
        )


# ── Event builder helpers ────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_provider_selected(
    provider: str,
    dry_run: bool,
    feature_flag_checked: bool,
    feature_flag_enabled: bool,
    *,
    repo: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SafetyEvent:
    """Record: which provider was selected and why."""
    return SafetyEvent(
        event_type=SafetyEventType.PROVIDER_SELECTED,
        timestamp=_now(),
        provider=provider,
        dry_run=dry_run,
        feature_flag_checked=feature_flag_checked,
        feature_flag_enabled=feature_flag_enabled,
        repo=repo,
        metadata=metadata or {},
    )


def build_write_guard_passed(
    provider: str,
    dry_run: bool,
    target_branch: str,
    operation_count: int,
    file_count: int,
    risk_level: str,
    *,
    repo: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SafetyEvent:
    """Record: WriteGuard passed all checks."""
    return SafetyEvent(
        event_type=SafetyEventType.WRITE_GUARD_PASSED,
        timestamp=_now(),
        provider=provider,
        dry_run=dry_run,
        branch=target_branch,
        operation_count=operation_count,
        file_count=file_count,
        risk_level=risk_level,
        repo=repo,
        metadata=metadata or {},
    )


def build_write_guard_blocked(
    provider: str,
    dry_run: bool,
    reason_code: str,
    target_branch: str,
    blocked_paths: list[str] | None = None,
    blocked_operations: list[str] | None = None,
    *,
    repo: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SafetyEvent:
    """Record: WriteGuard blocked the operation (no provider called)."""
    return SafetyEvent(
        event_type=SafetyEventType.WRITE_GUARD_BLOCKED,
        timestamp=_now(),
        provider=provider,
        dry_run=dry_run,
        branch=target_branch,
        reason_code=reason_code,
        blocked_paths=blocked_paths or [],
        blocked_operations=blocked_operations or [],
        repo=repo,
        metadata=metadata or {},
    )


def build_branch_created(
    provider: str,
    dry_run: bool,
    branch: str,
    base_branch: str,
    *,
    repo: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SafetyEvent:
    """Record: branch was created (or verified existing)."""
    return SafetyEvent(
        event_type=SafetyEventType.BRANCH_CREATED,
        timestamp=_now(),
        provider=provider,
        dry_run=dry_run,
        branch=branch,
        base_branch=base_branch,
        repo=repo,
        metadata=metadata or {},
    )


def build_commit_created(
    provider: str,
    dry_run: bool,
    branch: str,
    commit_sha: str,
    file_count: int,
    *,
    repo: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SafetyEvent:
    """Record: commit was created."""
    return SafetyEvent(
        event_type=SafetyEventType.COMMIT_CREATED,
        timestamp=_now(),
        provider=provider,
        dry_run=dry_run,
        branch=branch,
        commit_sha=commit_sha,
        file_count=file_count,
        repo=repo,
        metadata=metadata or {},
    )


def build_pr_opened(
    provider: str,
    dry_run: bool,
    branch: str,
    base_branch: str,
    pr_number: int,
    pr_url: str,
    title: str,
    *,
    repo: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SafetyEvent:
    """Record: PR was opened."""
    return SafetyEvent(
        event_type=SafetyEventType.PR_OPENED,
        timestamp=_now(),
        provider=provider,
        dry_run=dry_run,
        branch=branch,
        base_branch=base_branch,
        pr_number=pr_number,
        pr_url=pr_url,
        title=title,
        repo=repo,
        metadata=metadata or {},
    )