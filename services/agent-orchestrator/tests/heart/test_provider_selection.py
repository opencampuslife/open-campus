"""Tests for GitHub provider config and selector (P3-D)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HEART_SRC = Path(__file__).resolve().parents[2] / "src" / "heart"
if str(_HEART_SRC.parent) not in sys.path:
    sys.path.insert(0, str(_HEART_SRC.parent))

from heart.providers import (
    FakeGitHubAdapter,
    GitHubProviderConfig,
    RealGitHubAdapter,
    select_git_provider,
)
from heart.providers.github_errors import FeatureFlagDisabled


# ── GitHubProviderConfig defaults ─────────────────────────────────────────────

class TestGitHubProviderConfigDefaults:
    def test_defaults_write_disabled(self):
        """Real writes are off by default — safety default."""
        config = GitHubProviderConfig()
        assert config.github_write_enabled is False
        assert config.provider == "fake"
        assert config.github_token == ""

    def test_is_real_enabled_false_by_default(self):
        config = GitHubProviderConfig()
        assert config.is_real_enabled() is False
        assert config.can_real_write() is False

    def test_github_token_not_set(self):
        config = GitHubProviderConfig()
        assert config.github_token == ""

    def test_summary_shows_defaults(self):
        config = GitHubProviderConfig()
        summary = config.summary()
        assert "write_enabled=False" in summary
        assert "provider='fake'" in summary


# ── GitHubProviderConfig with env vars ─────────────────────────────────────────

class TestGitHubProviderConfigEnvVars:
    def test_env_overrides_defaults(self, monkeypatch):
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        monkeypatch.setenv("HEART_GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("HEART_GITHUB_OWNER", "test-org")
        monkeypatch.setenv("HEART_GITHUB_REPO", "test-repo")
        config = GitHubProviderConfig()
        assert config.github_write_enabled is True
        assert config.provider == "real"
        assert config.github_token == "ghp_test"
        assert config.github_owner == "test-org"
        assert config.github_repo == "test-repo"

    def test_is_real_enabled_with_full_credentials(self, monkeypatch):
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        monkeypatch.setenv("HEART_GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("HEART_GITHUB_OWNER", "test-org")
        monkeypatch.setenv("HEART_GITHUB_REPO", "test-repo")
        config = GitHubProviderConfig()
        assert config.is_real_enabled() is True
        assert config.can_real_write() is True

    def test_partial_credentials_not_enabled(self, monkeypatch):
        """Even with flag on, missing token/owner/repo means not real-enabled."""
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        # token missing
        config = GitHubProviderConfig()
        assert config.can_real_write() is False


# ── select_git_provider ───────────────────────────────────────────────────────

class TestSelectGitProvider:
    def test_fake_returns_fake_adapter(self):
        config = GitHubProviderConfig()
        adapter = select_git_provider(config, "fake")
        assert isinstance(adapter, FakeGitHubAdapter)

    def test_fake_does_not_check_flag(self):
        """fake provider works even when flag is off."""
        config = GitHubProviderConfig()
        assert config.github_write_enabled is False
        adapter = select_git_provider(config, "fake")
        assert isinstance(adapter, FakeGitHubAdapter)

    def test_real_flag_off_raises(self):
        """provider=real but flag off raises FeatureFlagDisabled."""
        config = GitHubProviderConfig()
        assert config.github_write_enabled is False
        with pytest.raises(FeatureFlagDisabled) as exc_info:
            select_git_provider(config, "real")
        assert "HEART_GITHUB_WRITE_ENABLED=1 required" in str(exc_info.value)
        assert exc_info.value.requested_provider == "real"

    def test_real_flag_on_missing_credentials_raises(self, monkeypatch):
        """Flag on but missing token/owner/repo raises FeatureFlagDisabled."""
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        # token missing
        config = GitHubProviderConfig()
        with pytest.raises(FeatureFlagDisabled) as exc_info:
            select_git_provider(config, "real")
        assert "<missing>" in str(exc_info.value)

    def test_real_full_credentials_returns_real_adapter(self, monkeypatch):
        """Flag on + full credentials → RealGitHubAdapter."""
        monkeypatch.setenv("HEART_GITHUB_WRITE_ENABLED", "1")
        monkeypatch.setenv("HEART_GITHUB_PROVIDER", "real")
        monkeypatch.setenv("HEART_GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("HEART_GITHUB_OWNER", "test-org")
        monkeypatch.setenv("HEART_GITHUB_REPO", "test-repo")
        config = GitHubProviderConfig()
        adapter = select_git_provider(config, "real")
        assert isinstance(adapter, RealGitHubAdapter)

    def test_unknown_provider_raises(self):
        config = GitHubProviderConfig()
        with pytest.raises(ValueError, match="unknown Git provider"):
            select_git_provider(config, "github")

    def test_unknown_provider_shows_value(self):
        config = GitHubProviderConfig()
        with pytest.raises(ValueError, match="'unknown'"):
            select_git_provider(config, "unknown")
