"""WriteGuard — security gate for GitHub write operations.

P3-C scope: block dangerous paths/branches/operations.
FakeGitHubAdapter only. No real GitHub API calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ── Forbidden patterns ────────────────────────────────────────────────────────

# Protected branch names — never allowed as write targets
PROTECTED_BRANCHES: frozenset[str] = frozenset({
    "main", "master", "production", "release", "stable",
})

# Forbidden file/path patterns (regex strings)
FORBIDDEN_PATH_PATTERNS: list[str] = [
    r"\.env",
    r"\.env\.",
    r"env\.local",
    r"/secrets?/",
    r"/secret/",
    r"secrets?",
    r"/auth/",
    r"/oauth/",
    r"/credentials",
    r"credentials\.json",
    r"/deploy/",
    r"deploy/",
    r"/infra/",
    r"/terraform/",
    r"/compliance/",
    r"\.github/workflows/",
    r"\.github/actions/",
    r"\.github/secrets",
    r"/\.github/",
    r"\.gitignore",
    r"\.gitattributes",
    r"package-lock\.json",
    r"yarn\.lock",
    r"\bGemfile\.lock\b",
    r"poetry\.lock",
    r"/ci/",
    r"/\.env",
    r"settings\.py",
    r"config\.py",
    r"\.pem",
    r"\.key",
    r"\.crt",
    r"\.p12",
    r"\.pfx",
    r"\.jks",
    r"\bpassword\b",
    r"\btoken\b",
    r"\bsecret\b",
    r"\bapikey\b",
    r"api[_-]?key",
]

# Compiled patterns for fast matching
_COMPILED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATH_PATTERNS
]

# Max file size: 512KB per file
MAX_FILE_SIZE_BYTES: int = 512 * 1024

# Forbidden operations
FORBIDDEN_OPERATIONS: frozenset[str] = frozenset({
    "merge", "delete_branch", "delete_file", "push_main",
    "force_push", "delete_tag", "update_release",
    "modify_secret", "modify_auth_policy", "modify_deploy_config",
    "modify_compliance_rule", "admin_permissions",
})


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class WriteGuardResult:
    """Result of a WriteGuard check."""
    allowed: bool
    reason: str | None = None
    code: str | None = None  # "path_blocked", "branch_blocked", "op_blocked", "risk_blocked", "size_blocked", "approval_required"

    @classmethod
    def ok(cls) -> "WriteGuardResult":
        return cls(allowed=True, reason=None, code=None)

    @classmethod
    def blocked(cls, reason: str, code: str) -> "WriteGuardResult":
        return cls(allowed=False, reason=reason, code=code)


# ── WriteGuard ───────────────────────────────────────────────────────────────

class WriteGuard:
    """Security gate for GitHub write operations.

    Checks branch name, file paths, operation type, file size, and risk level.
    All checks are additive — a single block is enough to reject.
    """

    def check_branch(self, branch: str) -> WriteGuardResult:
        """Reject writes to protected branches."""
        if branch in PROTECTED_BRANCHES:
            return WriteGuardResult.blocked(
                f"branch '{branch}' is protected and cannot be a write target",
                code="branch_blocked",
            )
        # also reject any branch that contains protected names as substring
        lower = branch.lower()
        for protected in PROTECTED_BRANCHES:
            if lower == protected or lower.startswith(f"{protected}/"):
                return WriteGuardResult.blocked(
                    f"branch '{branch}' matches protected pattern '{protected}'",
                    code="branch_blocked",
                )
        return WriteGuardResult.ok()

    def check_paths(self, paths: list[str]) -> WriteGuardResult:
        """Reject writes to forbidden file paths."""
        for path in paths:
            if self._path_is_forbidden(path):
                return WriteGuardResult.blocked(
                    f"file path '{path}' matches a forbidden pattern",
                    code="path_blocked",
                )
        return WriteGuardResult.ok()

    def check_operation(self, operation: str) -> WriteGuardResult:
        """Reject forbidden operations."""
        op_lower = operation.lower()
        if op_lower in FORBIDDEN_OPERATIONS:
            return WriteGuardResult.blocked(
                f"operation '{operation}' is not permitted",
                code="op_blocked",
            )
        return WriteGuardResult.ok()

    def check_file_size(self, content: bytes) -> WriteGuardResult:
        """Reject files exceeding max size."""
        if len(content) > MAX_FILE_SIZE_BYTES:
            return WriteGuardResult.blocked(
                f"file size {len(content)} exceeds max {MAX_FILE_SIZE_BYTES}",
                code="size_blocked",
            )
        return WriteGuardResult.ok()

    def check_risk_level(self, risk_level: str) -> WriteGuardResult:
        """Reject critical risk tasks from any write operation."""
        lower = risk_level.lower()
        if lower == "critical":
            return WriteGuardResult.blocked(
                "critical risk tasks are not eligible for write operations",
                code="risk_blocked",
            )
        # high risk: dry-run only (allow inspection, block apply)
        if lower == "high":
            return WriteGuardResult.blocked(
                "high risk tasks can only be dry-run, not applied",
                code="risk_blocked",
            )
        return WriteGuardResult.ok()

    def check_approval(self, has_approval: bool) -> WriteGuardResult:
        """Reject if no approval record exists."""
        if not has_approval:
            return WriteGuardResult.blocked(
                "no approval record found — write operations require approval",
                code="approval_required",
            )
        return WriteGuardResult.ok()

    def check_execution_plan(self, has_plan: bool) -> WriteGuardResult:
        """Reject if no execution plan exists."""
        if not has_plan:
            return WriteGuardResult.blocked(
                "no execution plan found — apply_execution_plan requires a plan",
                code="missing_plan",
            )
        return WriteGuardResult.ok()

    def check_all(
        self,
        *,
        branch: str | None = None,
        paths: list[str] | None = None,
        operation: str | None = None,
        content: bytes | None = None,
        risk_level: str | None = None,
        has_approval: bool | None = None,
        has_plan: bool | None = None,
    ) -> WriteGuardResult:
        """Run all applicable checks in order. Returns first failure."""
        checks = [
            ("branch", branch, self.check_branch),
            ("operation", operation, self.check_operation),
            ("paths", paths, lambda p: self.check_paths(p or [])),
            ("content", content, lambda c: self.check_file_size(c) if c else WriteGuardResult.ok()),
            ("risk", risk_level, lambda r: self.check_risk_level(r) if r else WriteGuardResult.ok()),
            ("approval", has_approval, lambda a: self.check_approval(a) if a is not None else WriteGuardResult.ok()),
            ("plan", has_plan, lambda p: self.check_execution_plan(p) if p is not None else WriteGuardResult.ok()),
        ]
        for name, value, fn in checks:
            if value is not None:
                result = fn(value)
                if not result.allowed:
                    return result
        return WriteGuardResult.ok()

    def _path_is_forbidden(self, path: str) -> bool:
        """Check if a path matches any forbidden pattern."""
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(path):
                return True
        return False