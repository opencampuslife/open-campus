"""Tests for audit.py — AuditReport builder and report_from_delivery_evidence.

P3-E scope: report assembly from delivery evidence, status determination.
"""

from __future__ import annotations

import pytest

from heart.audit import (
    AuditReport,
    AuditStatus,
    build_report,
    report_from_delivery_evidence,
)
from heart.safety_events import (
    SafetyEvent,
    SafetyEventType,
    build_branch_created,
    build_commit_created,
    build_pr_opened,
    build_provider_selected,
    build_write_guard_blocked,
    build_write_guard_passed,
)


class TestAuditStatus:
    def test_all_4_statuses_defined(self):
        assert AuditStatus.PASSED.value == "passed"
        assert AuditStatus.BLOCKED.value == "blocked"
        assert AuditStatus.PARTIAL.value == "partial"
        assert AuditStatus.NO_EVENTS.value == "no_events"


class TestAuditReportSerialization:
    def test_to_dict_roundtrip(self):
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_passed("fake", True, "heart/test", 1, 1, "low"),
            build_branch_created("fake", True, "heart/test", "main"),
        ]
        report = build_report(
            task_id="task_123",
            events=events,
            branch="heart/test",
            file_count=1,
        )
        d = report.to_dict()
        assert d["task_id"] == "task_123"
        assert d["status"] == "passed"
        assert d["provider"] == "fake"
        assert d["dry_run"] is True
        assert d["branch"] == "heart/test"
        assert len(d["events"]) == 3
        assert d["generated_at"]  # auto-generated

    def test_from_dict_roundtrip(self):
        events = [
            build_provider_selected("real", False, True, True),
            build_branch_created("real", False, "heart/test", "main"),
            build_commit_created("real", False, "heart/test", "sha123", 3),
            build_pr_opened("real", False, "heart/test", "main", 42, "https://x.com/42", "Title"),
        ]
        report = build_report(
            task_id="task_456",
            events=events,
            branch="heart/test",
            base_branch="main",
            commit_sha="sha123",
            file_count=3,
            pr_number=42,
            pr_url="https://x.com/42",
        )
        d = report.to_dict()
        restored = AuditReport.from_dict(d)
        assert restored.task_id == "task_456"
        assert restored.status == AuditStatus.PASSED
        assert restored.pr_number == 42


class TestBuildReportStatus:
    def test_no_events_returns_no_events_status(self):
        report = build_report("task_x", [])
        assert report.status == AuditStatus.NO_EVENTS

    def test_write_guard_blocked_returns_blocked_status(self):
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_blocked("fake", True, "branch_blocked", "main"),
        ]
        report = build_report("task_x", events)
        assert report.status == AuditStatus.BLOCKED

    def test_write_guard_passed_only_returns_partial(self):
        # guard passed but no actual write ops (branch/commit/PR) → partial
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_passed("fake", True, "heart/test", 1, 1, "low"),
        ]
        report = build_report("task_x", events)
        assert report.status == AuditStatus.PARTIAL

    def test_branch_created_returns_passed(self):
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_passed("fake", True, "heart/test", 1, 1, "low"),
            build_branch_created("fake", True, "heart/test", "main"),
        ]
        report = build_report("task_x", events)
        assert report.status == AuditStatus.PASSED

    def test_commit_created_returns_passed(self):
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_passed("fake", True, "heart/test", 1, 1, "low"),
            build_commit_created("fake", True, "heart/test", "sha123", 1),
        ]
        report = build_report("task_x", events)
        assert report.status == AuditStatus.PASSED

    def test_pr_opened_returns_passed(self):
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_passed("fake", True, "heart/test", 1, 1, "low"),
            build_pr_opened("fake", True, "heart/test", "main", 1, "https://x.com/1", "T"),
        ]
        report = build_report("task_x", events)
        assert report.status == AuditStatus.PASSED


class TestBuildReportFields:
    def test_provider_and_dry_run_from_first_event(self):
        events = [
            build_provider_selected("real", False, True, True),
            build_branch_created("real", False, "heart/test", "main"),
        ]
        report = build_report("task_x", events)
        assert report.provider == "real"
        assert report.dry_run is False

    def test_branch_from_first_branch_created(self):
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_passed("fake", True, "heart/test", 1, 1, "low"),
            build_branch_created("fake", True, "heart/test", "main"),
        ]
        report = build_report("task_x", events, branch="heart/feature-xyz")
        assert report.branch == "heart/feature-xyz"

    def test_blocked_reason_from_guard_blocked_event(self):
        events = [
            build_provider_selected("fake", True, False, False),
            build_write_guard_blocked("fake", True, "file_size_exceeded", "main"),
        ]
        report = build_report("task_x", events)
        assert report.blocked_reason == "file_size_exceeded"


class TestReportFromDeliveryEvidence:
    def test_full_delivery_evidence(self):
        evidence = {
            "task_id": "task_789",
            "dry_run": False,
            "provider": "fake",
            "safety_events": [
                build_provider_selected("fake", False, True, True).to_dict(),
                build_write_guard_passed("fake", False, "heart/test", 2, 2, "medium").to_dict(),
                build_branch_created("fake", False, "heart/test", "main").to_dict(),
                build_commit_created("fake", False, "heart/test", "sha999", 2).to_dict(),
                build_pr_opened("fake", False, "heart/test", "main", 99, "https://x.com/99", "Test PR").to_dict(),
            ],
            "git_results": {
                "create_branch": {"success": True, "data": {"branch": "heart/test"}},
                "commit_files": {"success": True, "data": {"commit_sha": "sha999"}},
                "open_pr": {"success": True, "data": {"pr_number": 99, "url": "https://x.com/99"}},
            },
        }
        report = report_from_delivery_evidence(evidence)
        assert report.task_id == "task_789"
        assert report.status == AuditStatus.PASSED
        assert report.provider == "fake"
        assert report.dry_run is False
        assert len(report.events) == 5
        assert report.commit_sha == "sha999"
        assert report.pr_number == 99
        assert report.pr_url == "https://x.com/99"

    def test_blocked_evidence(self):
        evidence = {
            "task_id": "task_blocked",
            "dry_run": True,
            "provider": "fake",
            "blocked": True,
            "safety_events": [
                build_provider_selected("fake", True, False, False).to_dict(),
                build_write_guard_blocked("fake", True, "branch_blocked", "main").to_dict(),
            ],
        }
        report = report_from_delivery_evidence(evidence)
        assert report.status == AuditStatus.BLOCKED
        assert report.blocked_reason == "branch_blocked"

    def test_empty_events_returns_no_events(self):
        evidence = {
            "task_id": "task_empty",
            "dry_run": True,
            "provider": "",
            "safety_events": [],
        }
        report = report_from_delivery_evidence(evidence)
        assert report.status == AuditStatus.NO_EVENTS