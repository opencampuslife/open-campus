"""Audit report — assembled from SafetyEvents stored in delivery evidence.

P3-E scope: report builder + data models. No new tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .safety_events import SafetyEvent, SafetyEventType


# ── Report status ────────────────────────────────────────────────────────────

class AuditStatus(Enum):
    """Overall audit result for a task's write operation."""
    PASSED = "passed"
    BLOCKED = "blocked"
    PARTIAL = "partial"  # some events succeeded, some blocked
    NO_EVENTS = "no_events"


# ── Report dataclass ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AuditReport:
    """A complete audit report for a single apply_execution_plan call.

    Assembled from SafetyEvents stored in delivery_evidence.
    This is a read-only view — it does not change any task state.
    """
    task_id: str
    status: AuditStatus
    provider: str
    dry_run: bool
    events: list[SafetyEvent] = field(default_factory=list)

    # Computed fields
    branch: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    file_count: int | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    blocked_reason: str | None = None

    generated_at: str = field(default="")
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Auto-generate timestamp if empty
        if not self.generated_at:
            object.__setattr__(self, "generated_at", datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "provider": self.provider,
            "dry_run": self.dry_run,
            "events": [e.to_dict() for e in self.events],
            "branch": self.branch,
            "base_branch": self.base_branch,
            "commit_sha": self.commit_sha,
            "file_count": self.file_count,
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "blocked_reason": self.blocked_reason,
            "generated_at": self.generated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditReport:
        events = [SafetyEvent.from_dict(e) for e in data.get("events", [])]
        return cls(
            task_id=data["task_id"],
            status=AuditStatus(data["status"]),
            provider=data["provider"],
            dry_run=data["dry_run"],
            events=events,
            branch=data.get("branch"),
            base_branch=data.get("base_branch"),
            commit_sha=data.get("commit_sha"),
            file_count=data.get("file_count"),
            pr_number=data.get("pr_number"),
            pr_url=data.get("pr_url"),
            blocked_reason=data.get("blocked_reason"),
            generated_at=data.get("generated_at", ""),
            metadata=data.get("metadata", {}),
        )


# ── Report builder ──────────────────────────────────────────────────────────

def build_report(
    task_id: str,
    events: list[SafetyEvent],
    *,
    branch: str | None = None,
    base_branch: str | None = None,
    commit_sha: str | None = None,
    file_count: int | None = None,
    pr_number: int | None = None,
    pr_url: str | None = None,
    blocked_reason: str | None = None,
) -> AuditReport:
    """Build an AuditReport from a list of SafetyEvents.

    Status logic:
    - No events → NO_EVENTS
    - Any WRITE_GUARD_BLOCKED → BLOCKED (provider never called)
    - All events are write operations → PASSED (or PARTIAL if some failed)
    - Mix of passed and blocked → PARTIAL
    """
    if not events:
        return AuditReport(
            task_id=task_id,
            status=AuditStatus.NO_EVENTS,
            provider="",
            dry_run=True,
        )

    # Provider and dry_run from the first event (should be consistent)
    provider = events[0].provider
    dry_run = events[0].dry_run

    # Determine status
    has_blocked = any(e.event_type == SafetyEventType.WRITE_GUARD_BLOCKED for e in events)
    has_write_ops = any(
        e.event_type in (
            SafetyEventType.BRANCH_CREATED,
            SafetyEventType.COMMIT_CREATED,
            SafetyEventType.PR_OPENED,
        )
        for e in events
    )

    if has_blocked:
        status = AuditStatus.BLOCKED
        # Extract blocked reason from the first WRITE_GUARD_BLOCKED event
        _blocked_reason: str | None = None
        for e in events:
            if e.event_type == SafetyEventType.WRITE_GUARD_BLOCKED and e.reason_code:
                _blocked_reason = e.reason_code
                break
        blocked_reason = _blocked_reason
    elif has_write_ops:
        status = AuditStatus.PASSED
    else:
        status = AuditStatus.PARTIAL
        blocked_reason = None

    return AuditReport(
        task_id=task_id,
        status=status,
        provider=provider,
        dry_run=dry_run,
        events=events,
        branch=branch,
        base_branch=base_branch,
        commit_sha=commit_sha,
        file_count=file_count,
        pr_number=pr_number,
        pr_url=pr_url,
        blocked_reason=blocked_reason,
    )


def report_from_delivery_evidence(evidence: dict[str, Any]) -> AuditReport:
    """Build an AuditReport from a delivery_evidence dict.

    The delivery_evidence is stored as JSON in the events table.
    This function reconstructs a report from that stored structure.

    Expected evidence structure (P3-C/P3-D):
    {
        "task_id": str,
        "dry_run": bool,
        "provider": str,
        "safety_events": [...SafetyEvent dicts...],
        "git_results": {...},
        "delivery_id": str,
    }

    Also handles the nested "payload" format returned by get_delivery_evidence().
    """
    # Unwrap nested payload if present (from get_delivery_evidence)
    inner = evidence.get("payload", evidence)

    task_id = inner.get("task_id", "unknown")

    raw_events = inner.get("safety_events", [])
    events = [SafetyEvent.from_dict(e) for e in raw_events]

    git_results = inner.get("git_results", {})
    # Extract from nested {op_name: {success, data: {...}}} structure
    git_data = git_results.get("create_branch", {}).get("data", {}) if isinstance(git_results.get("create_branch"), dict) else git_results
    commit_data = git_results.get("commit_files", {}).get("data", {}) if isinstance(git_results.get("commit_files"), dict) else {}
    pr_data = git_results.get("open_pr", {}).get("data", {}) if isinstance(git_results.get("open_pr"), dict) else {}
    branch = git_data.get("branch") or inner.get("branch")
    base_branch = git_data.get("base_branch") or git_data.get("base") or inner.get("base_branch")
    commit_sha = commit_data.get("commit_sha") or inner.get("commit_sha")
    file_count = commit_data.get("file_count") or inner.get("file_count")
    pr_number = pr_data.get("pr_number") or inner.get("pr_number")
    pr_url = pr_data.get("url") or pr_data.get("pr_url") or inner.get("pr_url")

    # Check for guard blocks in events
    blocked_reason = None
    for e in events:
        if e.event_type == SafetyEventType.WRITE_GUARD_BLOCKED:
            blocked_reason = e.reason_code
            break

    return build_report(
        task_id=task_id,
        events=events,
        branch=branch,
        base_branch=base_branch,
        commit_sha=commit_sha,
        file_count=file_count,
        pr_number=pr_number,
        pr_url=pr_url,
        blocked_reason=blocked_reason,
    )