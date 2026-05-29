"""P4-A: FastAPI HTTP adapter for Heart Mode.

Thin adapter — zero business logic. Every endpoint delegates directly
to HeartAPI and maps Python exceptions to HTTP error codes.

Design:
    - create_app(api=...) accepts a pre-built HeartAPI for testing.
    - create_app(config=...) creates a HeartAPI from config for production.
    - Error mapping is centralized: HeartError → HTTP status codes.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api import HeartAPI
from .errors import (
    ApprovalRejected,
    ApprovalRequired,
    EvidenceGateFailed,
    HeartError,
    InvalidTransition,
    TaskAlreadyTerminal,
    TaskNotFound,
)
from .providers.github_errors import FeatureFlagDisabled, GitHubProviderError
from .service_config import HeartServiceConfig
from .service_models import (
    ApplyExecutionPlanRequest,
    ApproveTaskRequest,
    CreateTaskRequest,
    ErrorResponse,
)
from .store import HeartStore, InMemoryHeartStore
from .store_sqlite import SQLiteHeartStore


# ── Error mapping ───────────────────────────────────────────────────────────
# Maps Python exception types to (HTTP status, error_code).
# Ordered: more specific → less specific. First match wins.

_ERROR_MAP: list[tuple[type, int, str]] = [
    (TaskNotFound, 404, "task_not_found"),
    (InvalidTransition, 409, "invalid_transition"),
    (ApprovalRequired, 409, "approval_required"),
    (ApprovalRejected, 403, "approval_rejected"),
    (EvidenceGateFailed, 422, "evidence_gate_failed"),
    (TaskAlreadyTerminal, 409, "task_already_terminal"),
    (FeatureFlagDisabled, 403, "feature_flag_disabled"),
    (GitHubProviderError, 502, "github_provider_error"),
]


def _map_exception(exc: Exception) -> tuple[int, str, str, dict]:
    """Map a Python exception to (status, code, message, details)."""
    for exc_type, status, code in _ERROR_MAP:
        if isinstance(exc, exc_type):
            return status, code, str(exc), _extract_details(exc)

    if isinstance(exc, ValueError):
        return 400, "bad_request", str(exc), {}
    if isinstance(exc, PermissionError):
        return 403, "forbidden", str(exc), {}
    return 500, "internal_error", str(exc), {}


def _extract_details(exc: Exception) -> dict:
    """Extract structured details from known exception types."""
    if isinstance(exc, TaskNotFound):
        return {"task_id": exc.task_id}
    if isinstance(exc, InvalidTransition):
        return {
            "task_id": exc.task_id,
            "current": exc.current,
            "target": exc.target,
        }
    if isinstance(exc, EvidenceGateFailed):
        return {"task_id": exc.task_id, "issues": exc.issues}
    if isinstance(exc, FeatureFlagDisabled):
        return {
            "requested_provider": exc.requested_provider,
        }
    return {}


# ── App factory ─────────────────────────────────────────────────────────────


def create_app(
    api: Optional[HeartAPI] = None,
    config: Optional[HeartServiceConfig] = None,
) -> FastAPI:
    """Create a FastAPI app for the Heart API HTTP service.

    Args:
        api: Pre-built HeartAPI instance. When provided, uses it directly
             (test mode — typically with InMemoryHeartStore).
        config: Service configuration. When api is None, creates HeartAPI
                from this config (production mode).

    Returns:
        Configured FastAPI application.
    """
    config = config or HeartServiceConfig.from_env()

    # ── Build HeartAPI ──────────────────────────────────────────────────
    if api is None:
        if config.store_type == "sqlite":
            store: HeartStore = SQLiteHeartStore(str(config.db_path))
        else:
            store = InMemoryHeartStore()
        api_instance = HeartAPI(store)
    else:
        api_instance = api

    # Inject config into GitHubConfig on HeartAPI for real-write checks
    if not config.github_write_enabled:
        api_instance._github_config.github_write_enabled = False

    app = FastAPI(
        title="Heart API Service",
        version="0.1.0",
        description="P4-A HTTP adapter for Heart Mode runtime.",
    )

    # ── Unified exception handler ───────────────────────────────────────
    # Catches all Python exceptions except HTTPException (FastAPI native).

    @app.exception_handler(HeartError)
    async def _handle_heart_error(request: Request, exc: HeartError):  # noqa: ARG001
        status, code, message, details = _map_exception(exc)
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                error={"code": code, "message": message, "details": details}
            ).model_dump(),
        )

    @app.exception_handler(GitHubProviderError)
    async def _handle_github_error(request: Request, exc: GitHubProviderError):  # noqa: ARG001
        status, code, message, details = _map_exception(exc)
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                error={"code": code, "message": message, "details": details}
            ).model_dump(),
        )

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError):  # noqa: ARG001
        status, code, message, details = _map_exception(exc)
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                error={"code": code, "message": message, "details": details}
            ).model_dump(),
        )

    @app.exception_handler(PermissionError)
    async def _handle_permission_error(request: Request, exc: PermissionError):  # noqa: ARG001
        status, code, message, details = _map_exception(exc)
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                error={"code": code, "message": message, "details": details}
            ).model_dump(),
        )

    # ── Endpoints ───────────────────────────────────────────────────────

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/heart/tasks")
    def create_task(req: CreateTaskRequest):
        request_dict = {
            "goal": req.goal,
            "risk_level": req.risk_level,
            "created_by": req.created_by,
            "acceptance_criteria": req.acceptance_criteria,
            "requires_human_approval": req.requires_human_approval,
        }
        return api_instance.create_task(request_dict)

    @app.get("/heart/tasks/{task_id}")
    def get_task(task_id: str):
        return api_instance.get_task(task_id)

    @app.get("/heart/tasks/{task_id}/events")
    def get_events(task_id: str):
        return api_instance.get_events(task_id)

    @app.post("/heart/tasks/{task_id}/approve")
    def approve_task(task_id: str, req: ApproveTaskRequest):
        request_dict = {
            "decision": req.decision,
            "approved_by": req.approved_by,
            "reason": req.reason,
            "modifications": req.modifications or [],
        }
        return api_instance.approve_task(task_id, request_dict)

    @app.post("/heart/tasks/{task_id}/plan-execution")
    def plan_execution(task_id: str):
        return api_instance.plan_execution(task_id)

    @app.post("/heart/tasks/{task_id}/apply-execution")
    def apply_execution(task_id: str, req: ApplyExecutionPlanRequest):
        request_dict = {
            "dry_run": req.dry_run,
            "provider": req.provider,
            "branch_name": req.branch_name,
        }
        return api_instance.apply_execution_plan(task_id, request_dict)

    @app.post("/heart/tasks/{task_id}/advance")
    def advance(task_id: str):
        return api_instance.advance(task_id)

    @app.get("/heart/tasks/{task_id}/audit-report")
    def audit_report(task_id: str):
        return api_instance.get_audit_report(task_id)

    return app
