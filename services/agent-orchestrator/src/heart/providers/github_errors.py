"""GitHub provider errors — P3-D scope only."""

from __future__ import annotations


class GitHubProviderError(Exception):
    """Base error for GitHub provider operations."""

    def __init__(self, message: str, operation: str | None = None) -> None:
        super().__init__(message)
        self.operation = operation


class FeatureFlagDisabled(GitHubProviderError):
    """Raised when real GitHub write is requested but feature flag is off.

    This is NOT a bug — it's the default safe behavior.
    """

    def __init__(
        self,
        requested_provider: str,
        reason: str = "HEART_GITHUB_WRITE_ENABLED=1 is required",
    ) -> None:
        super().__init__(
            f"real GitHub provider requested ({requested_provider!r}) but {reason}. "
            f"Real writes are disabled by default for safety.",
            operation="feature_flag",
        )
        self.requested_provider = requested_provider


class GitHubAPIError(GitHubProviderError):
    """Raised when the GitHub API returns an error response."""

    def __init__(self, operation: str, status_code: int, message: str) -> None:
        super().__init__(f"GitHub API error in {operation}: {status_code} {message}", operation)
        self.status_code = status_code
        self.api_message = message


class GitHubAuthError(GitHubAPIError):
    """Raised when GitHub API returns 401/403."""

    def __init__(self, message: str = "Invalid or missing GitHub token") -> None:
        super().__init__("auth", 401, message)


class GitHubBranchExistsError(GitHubProviderError):
    """Raised when trying to create a branch that already exists."""

    def __init__(self, branch: str) -> None:
        super().__init__(f"branch {branch!r} already exists", operation="create_branch")
        self.branch = branch


class GitHubRefNotFoundError(GitHubProviderError):
    """Raised when a branch/ref does not exist."""

    def __init__(self, ref: str) -> None:
        super().__init__(f"ref {ref!r} not found", operation="ref_lookup")
        self.ref = ref
