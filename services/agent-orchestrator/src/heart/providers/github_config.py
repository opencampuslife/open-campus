"""GitHub provider configuration — feature flag + env-based defaults.

P3-D scope: real GitHub provider behind HEART_GITHUB_WRITE_ENABLED=1.
Defaults to off; must be explicitly enabled.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class GitHubProviderConfig:
    """Configuration for GitHub write operations.

    All real GitHub operations are disabled by default.
    Must be explicitly enabled via env vars.
    """

    # Feature flag: master switch for ALL real GitHub write operations
    github_write_enabled: bool = field(
        default_factory=lambda: os.environ.get("HEART_GITHUB_WRITE_ENABLED", "0") == "1",
    )

    # Which provider to use: "fake" (default) | "real"
    provider: str = field(
        default_factory=lambda: os.environ.get("HEART_GITHUB_PROVIDER", "fake"),
    )

    # GitHub API settings (used by RealGitHubAdapter)
    github_api_url: str = field(
        default_factory=lambda: os.environ.get(
            "HEART_GITHUB_API_URL", "https://api.github.com"
        ),
    )
    github_token: str = field(
        default_factory=lambda: os.environ.get("HEART_GITHUB_TOKEN", ""),
    )
    github_owner: str = field(
        default_factory=lambda: os.environ.get("HEART_GITHUB_OWNER", ""),
    )
    github_repo: str = field(
        default_factory=lambda: os.environ.get("HEART_GITHUB_REPO", ""),
    )
    github_default_branch: str = field(
        default_factory=lambda: os.environ.get("HEART_GITHUB_DEFAULT_BRANCH", "main"),
    )

    def is_real_enabled(self) -> bool:
        """True only when real GitHub writes are explicitly allowed."""
        return (
            self.github_write_enabled
            and self.provider == "real"
            and bool(self.github_token)
            and bool(self.github_owner)
            and bool(self.github_repo)
        )

    def can_real_write(self) -> bool:
        """True when real write is requested AND enabled by flag."""
        return self.is_real_enabled()

    def summary(self) -> str:
        return (
            f"GitHubProviderConfig("
            f"write_enabled={self.github_write_enabled}, "
            f"provider={self.provider!r}, "
            f"owner={self.github_owner!r}, "
            f"repo={self.github_repo!r})"
        )
