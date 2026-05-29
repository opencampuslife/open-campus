"""Git provider interface and implementations.

P3-C scope: controlled write operations only.
P3-D adds: RealGitHubAdapter behind feature flag.

No real GitHub API calls by default (FakeGitHubAdapter).
"""

from __future__ import annotations

from typing import Any

from .fake_github import FakeGitHubAdapter
from .git_provider import FileChange, GitAdapter, GitOpResult
from .github_config import GitHubProviderConfig
from .github_errors import FeatureFlagDisabled, GitHubProviderError
from .mock_github import MockGitHubHTTPClient
from .real_github import RealGitHubAdapter, RequestsGitHubClient

__all__ = [
    "GitAdapter",
    "GitOpResult",
    "FileChange",
    "FakeGitHubAdapter",
    "RealGitHubAdapter",
    "RequestsGitHubClient",
    "MockGitHubHTTPClient",
    "GitHubProviderConfig",
    "GitHubProviderError",
    "FeatureFlagDisabled",
    "select_git_provider",
]


def select_git_provider(
    config: GitHubProviderConfig,
    requested_provider: str,
    *,
    http_client: Any = None,
) -> GitAdapter:
    """Select and return the appropriate Git provider.

    Args:
        config: GitHubProviderConfig with feature flag settings.
        requested_provider: "fake" | "real"
        http_client: optional inject for RealGitHubAdapter (used in tests).

    Returns:
        FakeGitHubAdapter when requested_provider == "fake"
        RealGitHubAdapter when requested_provider == "real" and flag enabled

    Raises:
        FeatureFlagDisabled: when real provider requested but flag is off
        ValueError: when requested_provider is unknown
    """
    if requested_provider == "fake":
        return FakeGitHubAdapter()

    if requested_provider == "real":
        if not config.github_write_enabled:
            raise FeatureFlagDisabled(
                requested_provider,
                reason=(
                    f"HEART_GITHUB_WRITE_ENABLED=1 required. "
                    f"Current: write_enabled={config.github_write_enabled}, "
                    f"provider={config.provider!r}"
                ),
            )
        if not config.can_real_write():
            raise FeatureFlagDisabled(
                requested_provider,
                reason=(
                    f"GitHub credentials incomplete. "
                    f"token={'<set>' if config.github_token else '<missing>'}, "
                    f"owner={config.github_owner!r}, repo={config.github_repo!r}"
                ),
            )
        return RealGitHubAdapter(config, http_client=http_client)

    raise ValueError(f"unknown Git provider: {requested_provider!r}. Use 'fake' or 'real'.")
