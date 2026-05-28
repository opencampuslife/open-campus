"""P4-A: HTTP request/response models for the Heart API service.

These are Pydantic models used by the FastAPI adapter — they define the
HTTP contract but contain ZERO business logic. All logic lives in HeartAPI.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Request models ─────────────────────────────────────────────────────────


class CreateTaskRequest(BaseModel):
    """POST /heart/tasks request body."""

    goal: str = Field(..., description="Task goal description", min_length=1)
    risk_level: str = Field("low", description="low|medium|high|critical")
    created_by: str = Field("system")
    acceptance_criteria: Optional[list[str]] = None
    requires_human_approval: Optional[bool] = None


class ApproveTaskRequest(BaseModel):
    """POST /heart/tasks/{task_id}/approve request body."""

    decision: str = Field(..., description="approved|rejected|modified")
    approved_by: str = Field(..., description="Who is approving")
    reason: Optional[str] = None
    modifications: Optional[list[str]] = None


class ApplyExecutionPlanRequest(BaseModel):
    """POST /heart/tasks/{task_id}/apply-execution request body."""

    dry_run: bool = True
    provider: str = "fake"
    branch_name: Optional[str] = None


# ── Response models ─────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    """Structured error payload."""

    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Uniform error response envelope."""

    error: ErrorDetail
