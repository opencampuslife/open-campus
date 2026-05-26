from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


class EventType:
    CHAT_RECEIVED = "chat.received"
    CHAT_ANSWERED = "chat.answered"
    RAG_RETRIEVED = "rag.retrieved"
    LLM_REQUESTED = "llm.requested"
    LLM_FAILED = "llm.failed"
    COMPLIANCE_BLOCKED = "compliance.blocked"
    PROFILE_UPDATED = "profile.updated"
    RECOMMENDATION_GENERATED = "recommendation.generated"
    LEAD_UPDATED = "lead.updated"
    HANDOFF_REQUESTED = "handoff.requested"
    ADMIN_SOURCE_UPLOADED = "admin.source.uploaded"
    ADMIN_STAGING_APPROVED = "admin.staging.approved"
    ADMIN_DOC_PUBLISHED = "admin.doc.published"
    GRAPH_RUN_STARTED = "graph.run.started"
    GRAPH_RUN_FAILED = "graph.run.failed"
    CAMPUS_AUTH_STATE_ISSUED = "campus.auth.state_issued"
    CAMPUS_AUTH_CALLBACK_SUCCEEDED = "campus.auth.callback_succeeded"
    CAMPUS_LEAVE_CREATED = "campus.leave.created"
    CAMPUS_LEAVE_APPROVED = "campus.leave.approved"
    CAMPUS_LEAVE_REJECTED = "campus.leave.rejected"
    CAMPUS_MEAL_CREATED = "campus.meal.created"
    CAMPUS_MEAL_CANCELLED = "campus.meal.cancelled"
    CAMPUS_MEAL_SUMMARY = "campus.meal.summary"
    CAMPUS_DELIVERY_CONFIRMED = "campus.delivery.confirmed"
    CAMPUS_REPAIR_CREATED = "campus.repair.created"
    CAMPUS_REPAIR_ASSIGNED = "campus.repair.assigned"
    CAMPUS_REPAIR_COMPLETED = "campus.repair.completed"
    CAMPUS_REPAIR_CLOSED = "campus.repair.closed"
    CAMPUS_REPAIR_TIMEOUT = "campus.repair.timeout"
    CAMPUS_DAILY_REPORT_GENERATED = "campus.daily_report.generated"
    SECURITY_CSRF_BLOCKED = "security.csrf_blocked"
    SECURITY_RATE_LIMITED = "security.rate_limited"
    SECURITY_SSRF_BLOCKED = "security.ssrf_blocked"

    ALL = frozenset({
        CHAT_RECEIVED, CHAT_ANSWERED, RAG_RETRIEVED, LLM_REQUESTED, LLM_FAILED,
        COMPLIANCE_BLOCKED, PROFILE_UPDATED, RECOMMENDATION_GENERATED, LEAD_UPDATED,
        HANDOFF_REQUESTED, ADMIN_SOURCE_UPLOADED, ADMIN_STAGING_APPROVED,
        ADMIN_DOC_PUBLISHED, GRAPH_RUN_STARTED, GRAPH_RUN_FAILED,
        CAMPUS_AUTH_STATE_ISSUED, CAMPUS_AUTH_CALLBACK_SUCCEEDED,
        CAMPUS_LEAVE_CREATED, CAMPUS_LEAVE_APPROVED, CAMPUS_LEAVE_REJECTED,
        CAMPUS_MEAL_CREATED, CAMPUS_MEAL_CANCELLED, CAMPUS_MEAL_SUMMARY,
        CAMPUS_DELIVERY_CONFIRMED, CAMPUS_REPAIR_CREATED, CAMPUS_REPAIR_ASSIGNED,
        CAMPUS_REPAIR_COMPLETED, CAMPUS_REPAIR_CLOSED, CAMPUS_REPAIR_TIMEOUT,
        CAMPUS_DAILY_REPORT_GENERATED,
        SECURITY_CSRF_BLOCKED, SECURITY_RATE_LIMITED, SECURITY_SSRF_BLOCKED,
    })

    CATEGORIES = {
        "chat": {CHAT_RECEIVED, CHAT_ANSWERED},
        "rag": {RAG_RETRIEVED},
        "llm": {LLM_REQUESTED, LLM_FAILED},
        "compliance": {COMPLIANCE_BLOCKED},
        "profile": {PROFILE_UPDATED},
        "recommendation": {RECOMMENDATION_GENERATED},
        "lead": {LEAD_UPDATED},
        "handoff": {HANDOFF_REQUESTED},
        "admin": {ADMIN_SOURCE_UPLOADED, ADMIN_STAGING_APPROVED, ADMIN_DOC_PUBLISHED},
        "graph": {GRAPH_RUN_STARTED, GRAPH_RUN_FAILED},
        "campus": {
            CAMPUS_AUTH_STATE_ISSUED, CAMPUS_AUTH_CALLBACK_SUCCEEDED,
            CAMPUS_LEAVE_CREATED, CAMPUS_LEAVE_APPROVED, CAMPUS_LEAVE_REJECTED,
            CAMPUS_MEAL_CREATED, CAMPUS_MEAL_CANCELLED, CAMPUS_MEAL_SUMMARY,
            CAMPUS_DELIVERY_CONFIRMED, CAMPUS_REPAIR_CREATED, CAMPUS_REPAIR_ASSIGNED,
            CAMPUS_REPAIR_COMPLETED, CAMPUS_REPAIR_CLOSED, CAMPUS_REPAIR_TIMEOUT,
            CAMPUS_DAILY_REPORT_GENERATED,
        },
        "security": {SECURITY_CSRF_BLOCKED, SECURITY_RATE_LIMITED, SECURITY_SSRF_BLOCKED},
    }

    ROLE_VISIBILITY = {
        "admin": ALL,
        "campus_admin": ALL,
        "sales": {
            CHAT_RECEIVED, CHAT_ANSWERED, PROFILE_UPDATED, LEAD_UPDATED,
            HANDOFF_REQUESTED, RECOMMENDATION_GENERATED,
        },
        "content_operator": {
            ADMIN_SOURCE_UPLOADED, ADMIN_STAGING_APPROVED, ADMIN_DOC_PUBLISHED,
            GRAPH_RUN_STARTED, GRAPH_RUN_FAILED,
            CAMPUS_AUTH_STATE_ISSUED, CAMPUS_AUTH_CALLBACK_SUCCEEDED,
            CAMPUS_LEAVE_CREATED, CAMPUS_LEAVE_APPROVED, CAMPUS_LEAVE_REJECTED,
            CAMPUS_MEAL_CREATED, CAMPUS_MEAL_CANCELLED, CAMPUS_MEAL_SUMMARY,
            CAMPUS_DELIVERY_CONFIRMED, CAMPUS_REPAIR_CREATED, CAMPUS_REPAIR_ASSIGNED,
            CAMPUS_REPAIR_COMPLETED, CAMPUS_REPAIR_CLOSED, CAMPUS_REPAIR_TIMEOUT,
            CAMPUS_DAILY_REPORT_GENERATED,
        },
        "reviewer": {
            ADMIN_STAGING_APPROVED, ADMIN_DOC_PUBLISHED,
        },
        "school_admin": ALL,
        "super_admin": ALL,
        "head_teacher": {
            CAMPUS_AUTH_CALLBACK_SUCCEEDED,
            CAMPUS_LEAVE_CREATED, CAMPUS_LEAVE_APPROVED, CAMPUS_LEAVE_REJECTED,
            CAMPUS_MEAL_SUMMARY,
            CAMPUS_REPAIR_CREATED, CAMPUS_REPAIR_ASSIGNED, CAMPUS_REPAIR_COMPLETED,
            CAMPUS_REPAIR_CLOSED, CAMPUS_REPAIR_TIMEOUT, CAMPUS_DAILY_REPORT_GENERATED,
        },
        "academic_staff": {
            CAMPUS_AUTH_CALLBACK_SUCCEEDED,
            CAMPUS_LEAVE_CREATED, CAMPUS_LEAVE_APPROVED, CAMPUS_LEAVE_REJECTED,
            CAMPUS_MEAL_SUMMARY, CAMPUS_DAILY_REPORT_GENERATED,
        },
        "logistics_staff": {
            CAMPUS_MEAL_SUMMARY, CAMPUS_DELIVERY_CONFIRMED,
            CAMPUS_REPAIR_CREATED, CAMPUS_REPAIR_ASSIGNED, CAMPUS_REPAIR_COMPLETED,
            CAMPUS_REPAIR_CLOSED, CAMPUS_REPAIR_TIMEOUT, CAMPUS_DAILY_REPORT_GENERATED,
        },
        "repair_assignee": {
            CAMPUS_REPAIR_CREATED, CAMPUS_REPAIR_ASSIGNED, CAMPUS_REPAIR_COMPLETED,
            CAMPUS_REPAIR_CLOSED, CAMPUS_REPAIR_TIMEOUT,
        },
        "vendor_link_user": {CAMPUS_DELIVERY_CONFIRMED},
        "parent_or_student_h5": {
            CAMPUS_AUTH_STATE_ISSUED, CAMPUS_LEAVE_CREATED, CAMPUS_MEAL_CREATED,
            CAMPUS_MEAL_CANCELLED, CAMPUS_REPAIR_CREATED,
        },
        "visitor": frozenset(),
        "parent": frozenset(),
        "student": frozenset(),
    }


@dataclass
class AuditEvent:
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: str = ""
    request_id: str = ""
    session_id: str = ""
    lead_id: str = ""
    user_id: str = ""
    role: str = ""
    campus: str = ""
    entrypoint: str = ""
    event_type: str = ""
    action: str = ""
    status: str = "ok"
    latency_ms: int = 0
    error_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    SENSITIVE_FIELDS = {"phone", "password", "api_key", "token", "secret"}

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["metadata"] = self._redact_metadata(d.get("metadata", {}))
        return d

    def _redact_metadata(self, md: dict[str, Any]) -> dict[str, Any]:
        if not md:
            return md
        cleaned: dict[str, Any] = {}
        for k, v in md.items():
            low = k.lower()
            if any(s in low for s in self.SENSITIVE_FIELDS):
                cleaned[k] = "[REDACTED]"
            elif isinstance(v, dict):
                cleaned[k] = self._redact_metadata(v)
            else:
                cleaned[k] = v
        return cleaned


def make_event(
    event_type: str,
    *,
    trace_id: str = "",
    request_id: str = "",
    session_id: str = "",
    lead_id: str = "",
    user_id: str = "",
    role: str = "",
    campus: str = "",
    entrypoint: str = "",
    action: str = "",
    status: str = "ok",
    latency_ms: int = 0,
    error_code: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        trace_id=trace_id,
        request_id=request_id,
        session_id=session_id,
        lead_id=lead_id,
        user_id=user_id,
        role=role,
        campus=campus,
        entrypoint=entrypoint,
        event_type=event_type,
        action=action or event_type,
        status=status,
        latency_ms=latency_ms,
        error_code=error_code,
        metadata=metadata or {},
    )
