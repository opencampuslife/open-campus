from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


class UntrustedProxyError(ValueError):
    """Raised when x-gaokao-* headers arrive from an untrusted source."""
    pass

# ── Role definitions ────────────────────────────────────────────

ROLE_ADMIN = "admin"
ROLE_CAMPUS_ADMIN = "campus_admin"
ROLE_CONTENT_OPERATOR = "content_operator"
ROLE_REVIEWER = "reviewer"
ROLE_SALES = "sales"

ALL_ADMIN_ROLES = {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR, ROLE_REVIEWER, ROLE_SALES}
KNOWLEDGE_ADMIN_ROLES = {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR, ROLE_REVIEWER}

# ── Action strings ──────────────────────────────────────────────

class Action:
    HEALTH_READ = "admin.health.read"
    SOURCE_UPLOAD = "knowledge.source.upload"
    STAGING_READ = "knowledge.staging.read"
    STAGING_EDIT = "knowledge.staging.edit"
    STAGING_EDIT_PERMISSION = "knowledge.staging.edit_permission_fields"
    STAGING_VALIDATE = "knowledge.staging.validate"
    STAGING_APPROVE = "knowledge.staging.approve"
    STAGING_REJECT = "knowledge.staging.reject"
    STAGING_PUBLISH = "knowledge.staging.publish"
    STAGING_DELETE = "knowledge.staging.delete"
    GRAPH_RUN = "knowledge.graph.run"
    GRAPH_READ = "knowledge.graph.read"
    INGESTION_RUN = "knowledge.ingestion.run"
    INGESTION_READ = "knowledge.ingestion.read"
    INGESTION_ENABLE_REMOTE = "knowledge.ingestion.enable_remote"
    CRM_LEAD_READ = "crm.lead.read"
    SALES_SESSION_READ = "sales.session.read"
    AUDIT_READ = "audit.read"
    BACKUP_RESTORE = "admin.backup.restore"
    ASSIGN_ADMIN = "admin.role.assign_admin"

# ── Action → allowed roles ──────────────────────────────────────

ACTION_ROLES: dict[str, set[str]] = {
    Action.HEALTH_READ:               {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR, ROLE_REVIEWER},
    Action.SOURCE_UPLOAD:             {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR},
    Action.STAGING_READ:              {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR, ROLE_REVIEWER},
    Action.STAGING_EDIT:              {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR},
    Action.STAGING_EDIT_PERMISSION:   {ROLE_ADMIN, ROLE_CAMPUS_ADMIN},
    Action.STAGING_VALIDATE:          {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR, ROLE_REVIEWER},
    Action.STAGING_APPROVE:           {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_REVIEWER},
    Action.STAGING_REJECT:            {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_REVIEWER},
    Action.STAGING_PUBLISH:           {ROLE_ADMIN, ROLE_CAMPUS_ADMIN},
    Action.STAGING_DELETE:            {ROLE_ADMIN, ROLE_CAMPUS_ADMIN},
    Action.GRAPH_RUN:                 {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR, ROLE_REVIEWER},
    Action.GRAPH_READ:                {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR, ROLE_REVIEWER},
    Action.INGESTION_RUN:             {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR},
    Action.INGESTION_READ:            {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_CONTENT_OPERATOR},
    Action.INGESTION_ENABLE_REMOTE:   {ROLE_ADMIN, ROLE_CAMPUS_ADMIN},
    Action.CRM_LEAD_READ:             {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_SALES},
    Action.SALES_SESSION_READ:        {ROLE_ADMIN, ROLE_CAMPUS_ADMIN, ROLE_SALES},
    Action.AUDIT_READ:                {ROLE_ADMIN, ROLE_CAMPUS_ADMIN},
    Action.BACKUP_RESTORE:            {ROLE_ADMIN},
    Action.ASSIGN_ADMIN:             {ROLE_ADMIN},
}

# ── Dangerous actions requiring explicit confirmation phrase ────

DANGEROUS_ACTION_CONFIRMATIONS: dict[str, str] = {
    Action.STAGING_PUBLISH:            "PUBLISH",
    Action.STAGING_DELETE:             "DELETE",
    Action.STAGING_EDIT_PERMISSION:    "CHANGE PERMISSION",
    Action.INGESTION_ENABLE_REMOTE:    "ENABLE URL INGESTION",
    Action.BACKUP_RESTORE:             "RESTORE",
    Action.ASSIGN_ADMIN:               "ASSIGN ADMIN",
}

_ACTION_DISPLAY_NAMES: dict[str, str] = {
    Action.STAGING_PUBLISH: "Publish document",
    Action.STAGING_DELETE: "Delete staging document",
    Action.STAGING_EDIT_PERMISSION: "Change permission fields",
    Action.INGESTION_ENABLE_REMOTE: "Enable remote URL ingestion",
    Action.BACKUP_RESTORE: "Restore from backup",
    Action.ASSIGN_ADMIN: "Assign admin role",
}

# ── Session expiry settings ─────────────────────────────────────

def _get_ttl_seconds() -> int:
    return int(os.environ.get("ADMIN_SESSION_TTL_SECONDS", "28800"))

def _get_idle_timeout_seconds() -> int:
    return int(os.environ.get("ADMIN_IDLE_TIMEOUT_SECONDS", "1800"))

# ── Permission fields that only admin/campus_admin can edit ─────

PROTECTED_PERMISSION_FIELDS = {
    "visibility",
    "allowed_roles",
    "data_level",
    "data_level_int",
    "campus_scope",
    "review_status",
}

# ── Admin Context ───────────────────────────────────────────────

@dataclass
class AdminContext:
    user_id: str
    role: str
    campus: str
    entrypoint: str = "admin_console"

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_campus_admin(self) -> bool:
        return self.role == ROLE_CAMPUS_ADMIN

    @property
    def is_knowledge_admin(self) -> bool:
        return self.role in KNOWLEDGE_ADMIN_ROLES

    @property
    def is_sales(self) -> bool:
        return self.role == ROLE_SALES

    def has_action(self, action: str) -> bool:
        allowed = ACTION_ROLES.get(action, set())
        return self.role in allowed

    def can_access_campus(self, resource_campus: str) -> bool:
        if self.is_admin:
            return True
        if resource_campus in (self.campus, "all"):
            return True
        if self.campus == "all":
            return True
        return False


def build_context(identity: dict[str, Any]) -> AdminContext:
    return AdminContext(
        user_id=str(identity.get("user_id", "anonymous")),
        role=str(identity.get("role", "visitor")),
        campus=str(identity.get("campus", "all")),
    )


# ── Enforcement ─────────────────────────────────────────────────

def require_action(ctx: AdminContext, action: str, resource: dict[str, Any] | None = None) -> None:
    """Raise ValueError if context is not authorized for the action."""
    if not ctx.has_action(action):
        raise ValueError(f"Action '{action}' denied for role: {ctx.role}")

    # Campus isolation: non-admin roles only see their campus
    if resource and not ctx.is_admin:
        resource_campus = resource.get("campus", resource.get("campus_scope", "all"))
        if isinstance(resource_campus, list):
            if ctx.campus not in resource_campus and "all" not in resource_campus:
                raise ValueError(f"Campus '{ctx.campus}' not in resource campus_scope: {resource_campus}")
        elif resource_campus not in (ctx.campus, "all") and ctx.campus != "all":
            raise ValueError(f"Campus '{ctx.campus}' cannot access campus '{resource_campus}'")


def require_action_str(identity: dict[str, Any], action: str, resource: dict[str, Any] | None = None) -> AdminContext:
    """Convenience: build context + enforce. Returns context for audit logging."""
    ctx = build_context(identity)
    require_action(ctx, action, resource)
    return ctx


def can_edit_permission_fields(ctx: AdminContext) -> bool:
    return ctx.has_action(Action.STAGING_EDIT_PERMISSION)


def is_permission_field(field_name: str) -> bool:
    return field_name in PROTECTED_PERMISSION_FIELDS


def can_view_audit(ctx: AdminContext) -> bool:
    return ctx.has_action(Action.AUDIT_READ)


def can_view_crm(ctx: AdminContext) -> bool:
    return ctx.has_action(Action.CRM_LEAD_READ)


def can_view_sales(ctx: AdminContext) -> bool:
    return ctx.has_action(Action.SALES_SESSION_READ)


def get_campus_filter(ctx: AdminContext) -> str | None:
    """Returns None for admin (no filter), campus name otherwise."""
    if ctx.is_admin:
        return None
    return ctx.campus


# ── Dangerous action confirmation ────────────────────────────────

def _normalize_confirmation(value: str) -> str:
    return value.strip().upper()

def validate_confirmation(action: str, confirmation: str) -> str | None:
    """Returns error message if confirmation fails, None if OK."""
    expected = DANGEROUS_ACTION_CONFIRMATIONS.get(action)
    if expected is None:
        return None
    normalized = _normalize_confirmation(confirmation)
    if normalized != expected:
        display = _ACTION_DISPLAY_NAMES.get(action, action)
        return f"dangerous action '{display}' requires confirmation phrase '{expected}'"
    return None

def is_dangerous_action(action: str) -> bool:
    return action in DANGEROUS_ACTION_CONFIRMATIONS

def get_confirmation_phrase(action: str) -> str | None:
    return DANGEROUS_ACTION_CONFIRMATIONS.get(action)


# ── Admin session expiry ─────────────────────────────────────────

_session_store: dict[str, dict[str, Any]] = {}

def record_admin_session_activity(user_id: str) -> None:
    now = time.time()
    if user_id not in _session_store:
        _session_store[user_id] = {"created_at": now, "last_active": now}
    _session_store[user_id]["last_active"] = now

def check_admin_session(user_id: str) -> str | None:
    """Returns error message if session expired, None if OK."""
    if user_id not in _session_store:
        return None
    session = _session_store[user_id]
    now = time.time()
    ttl = _get_ttl_seconds()
    idle = _get_idle_timeout_seconds()
    if now - session["created_at"] > ttl:
        return "admin session expired (absolute TTL)"
    if now - session["last_active"] > idle:
        return "admin session expired (idle timeout)"
    return None

def invalidate_admin_session(user_id: str) -> None:
    _session_store.pop(user_id, None)


# ── Trusted proxy identity header validation ─────────────────────

def validate_trusted_proxy(headers: dict[str, str]) -> str | None:
    """Returns error if identity headers come from untrusted source.
    Only enforced when GAOKAO_ENV=production or TRUSTED_PROXY_TOKEN is explicitly set.
    """
    identity_prefixes = ("x-gaokao-user-id", "x-gaokao-role", "x-gaokao-campus")
    lowered = {k.lower(): v for k, v in headers.items()}

    has_identity_headers = any(
        key in lowered for key in identity_prefixes
    )
    if not has_identity_headers:
        return None

    is_prod = os.environ.get("GAOKAO_ENV", "development") == "production"
    token_set = bool(os.environ.get("TRUSTED_PROXY_TOKEN", "").strip())
    if not is_prod and not token_set:
        return None

    trusted = lowered.get("x-gaokao-trusted-proxy", "").strip()
    expected = os.environ.get("TRUSTED_PROXY_TOKEN", "internal-gateway")

    if trusted != expected:
        return "untrusted proxy: x-gaokao-* identity headers require x-gaokao-trusted-proxy token"

    return None
