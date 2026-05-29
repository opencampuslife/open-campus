"""Tests for safety_events.py — normalized audit event builders.

P3-E scope: 6 event types, builder functions, serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from heart.safety_events import (
    SafetyEvent,
    SafetyEventType,
    build_branch_created,
    build_commit_created,
    build_provider_selected,
    build_pr_opened,
    build_write_guard_blocked,
    build_write_guard_passed,
)


class TestSafetyEventType:
    def test_all_6_types_defined(self):
        assert len(SafetyEventType) == 6
        assert SafetyEventType.PROVIDER_SELECTED.value == "provider_selected"
        assert SafetyEventType.WRITE_GUARD_PASSED.value == "write_guard_passed"
        assert SafetyEventType.WRITE_GUARD_BLOCKED.value == "write_guard_blocked"
        assert SafetyEventType.BRANCH_CREATED.value == "branch_created"
        assert SafetyEventType.COMMIT_CREATED.value == "commit_created"
        assert SafetyEventType.PR_OPENED.value == "pr_opened"

    def test_type_is_enum(self):
        assert isinstance(SafetyEventType.PROVIDER_SELECTED, SafetyEventType)


class TestSafetyEventSerialize:
    def test_to_dict_includes_all_fields(self):
        event = SafetyEvent(
            event_type=SafetyEventType.PROVIDER_SELECTED,
            timestamp="2026-05-28T12:00:00+00:00",
            provider="fake",
            dry_run=True,
            feature_flag_checked=True,
            feature_flag_enabled=False,
            repo="test-repo",
            metadata={"note": "test"},
        )
        d = event.to_dict()
        assert d["event_type"] == "provider_selected"
        assert d["timestamp"] == "2026-05-28T12:00:00+00:00"
        assert d["provider"] == "fake"
        assert d["dry_run"] is True
        assert d["feature_flag_checked"] is True
        assert d["feature_flag_enabled"] is False
        assert d["repo"] == "test-repo"
        assert d["metadata"] == {"note": "test"}

    def test_from_dict_roundtrip(self):
        original = build_provider_selected(
            provider="real",
            dry_run=False,
            feature_flag_checked=True,
            feature_flag_enabled=True,
            repo="my-repo",
            metadata={"key": "value"},
        )
        d = original.to_dict()
        restored = SafetyEvent.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.provider == original.provider
        assert restored.dry_run == original.dry_run
        assert restored.feature_flag_checked == original.feature_flag_checked
        assert restored.feature_flag_enabled == original.feature_flag_enabled
        assert restored.repo == original.repo
        assert restored.metadata == original.metadata

    def test_immutable_via_frozen(self):
        event = build_provider_selected("fake", True, False, False)
        with pytest.raises(Exception):  # frozen dataclass
            event.provider = "real"


class TestBuildProviderSelected:
    def test_required_fields(self):
        event = build_provider_selected(
            provider="fake",
            dry_run=True,
            feature_flag_checked=False,
            feature_flag_enabled=False,
        )
        assert event.event_type == SafetyEventType.PROVIDER_SELECTED
        assert event.provider == "fake"
        assert event.dry_run is True
        assert event.feature_flag_checked is False
        assert event.feature_flag_enabled is False
        assert event.timestamp  # auto-generated

    def test_optional_repo(self):
        event = build_provider_selected(
            provider="real",
            dry_run=False,
            feature_flag_checked=True,
            feature_flag_enabled=True,
            repo="test-org/test-repo",
        )
        assert event.repo == "test-org/test-repo"

    def test_optional_metadata(self):
        event = build_provider_selected(
            provider="fake",
            dry_run=True,
            feature_flag_checked=False,
            feature_flag_enabled=False,
            metadata={"extra": "info"},
        )
        assert event.metadata == {"extra": "info"}


class TestBuildWriteGuardPassed:
    def test_all_fields(self):
        event = build_write_guard_passed(
            provider="fake",
            dry_run=True,
            target_branch="heart/test-1234",
            operation_count=5,
            file_count=3,
            risk_level="medium",
            repo="my-repo",
        )
        assert event.event_type == SafetyEventType.WRITE_GUARD_PASSED
        assert event.branch == "heart/test-1234"
        assert event.operation_count == 5
        assert event.file_count == 3
        assert event.risk_level == "medium"
        assert event.repo == "my-repo"


class TestBuildWriteGuardBlocked:
    def test_reason_code_required(self):
        event = build_write_guard_blocked(
            provider="fake",
            dry_run=True,
            reason_code="branch_blocked",
            target_branch="main",
        )
        assert event.event_type == SafetyEventType.WRITE_GUARD_BLOCKED
        assert event.reason_code == "branch_blocked"
        assert event.branch == "main"

    def test_blocked_paths_and_operations(self):
        event = build_write_guard_blocked(
            provider="real",
            dry_run=False,
            reason_code="file_size_exceeded",
            target_branch="feature/test",
            blocked_paths=["large.bin", "huge.zip"],
            blocked_operations=["commit_files", "delete_file"],
        )
        assert event.blocked_paths == ["large.bin", "huge.zip"]
        assert event.blocked_operations == ["commit_files", "delete_file"]


class TestBuildBranchCreated:
    def test_required_fields(self):
        event = build_branch_created(
            provider="fake",
            dry_run=True,
            branch="heart/test-1234",
            base_branch="main",
        )
        assert event.event_type == SafetyEventType.BRANCH_CREATED
        assert event.branch == "heart/test-1234"
        assert event.base_branch == "main"


class TestBuildCommitCreated:
    def test_required_fields(self):
        event = build_commit_created(
            provider="fake",
            dry_run=True,
            branch="heart/test-1234",
            commit_sha="abc123def456",
            file_count=3,
        )
        assert event.event_type == SafetyEventType.COMMIT_CREATED
        assert event.commit_sha == "abc123def456"
        assert event.file_count == 3


class TestBuildPROpened:
    def test_required_fields(self):
        event = build_pr_opened(
            provider="fake",
            dry_run=True,
            branch="heart/test-1234",
            base_branch="main",
            pr_number=42,
            pr_url="https://github.com/org/repo/pull/42",
            title="Heart Mode: test",
        )
        assert event.event_type == SafetyEventType.PR_OPENED
        assert event.pr_number == 42
        assert event.pr_url == "https://github.com/org/repo/pull/42"
        assert event.title == "Heart Mode: test"

    def test_timestamp_auto_generated(self):
        event = build_pr_opened(
            provider="fake",
            dry_run=True,
            branch="heart/test",
            base_branch="main",
            pr_number=1,
            pr_url="https://github.com/org/repo/pull/1",
            title="Test",
        )
        # ISO format check
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))