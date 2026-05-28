"""P4-A: HTTP service tests — happy path + error path.

Tests the FastAPI adapter layer. All business logic tests live in
the HeartAPI test suite — these tests verify ONLY the HTTP contract:
    - Correct status codes
    - Correct error format
    - Endpoint routing
    - Request/response serialization

State machine realities (P2-A/P3):
    - Low-risk: create→intake, plan()→completed (auto). Cannot reach evidence_gate.
    - Medium-risk: create→intake, plan()→ready_for_approval, approve(), plan_execution()→evidence_gate.
    - High-risk: same as medium, but write_guard blocks apply_execution even in dry-run.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from heart.api import HeartAPI
from heart.service import create_app
from heart.store import InMemoryHeartStore


@pytest.fixture
def api() -> HeartAPI:
    """Fresh HeartAPI with in-memory store."""
    return HeartAPI(InMemoryHeartStore())


@pytest.fixture
def client(api: HeartAPI) -> TestClient:
    """Test client wrapping the FastAPI adapter."""
    app = create_app(api=api)
    return TestClient(app)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Healthz
# ──────────────────────────────────────────────────────────────────────────────


def test_healthz_returns_ok(client: TestClient):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────────────
# 2. Create + Get Task
# ──────────────────────────────────────────────────────────────────────────────


def test_create_and_get_task(client: TestClient):
    resp = client.post("/heart/tasks", json={"goal": "Fix login bug", "risk_level": "low"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal"] == "Fix login bug"
    assert data["risk_level"] == "low"
    assert data["status"] == "intake"  # engine auto-advances from task_created → intake
    task_id = data["task_id"]

    resp2 = client.get(f"/heart/tasks/{task_id}")
    assert resp2.status_code == 200
    assert resp2.json()["task_id"] == task_id
    assert resp2.json()["goal"] == "Fix login bug"


def test_create_task_defaults(client: TestClient):
    resp = client.post("/heart/tasks", json={"goal": "Default test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["created_by"] == "system"


def test_create_task_missing_goal_returns_422(client: TestClient):
    resp = client.post("/heart/tasks", json={})
    assert resp.status_code == 422  # Pydantic validation


def test_create_task_invalid_risk_level_returns_400(client: TestClient):
    resp = client.post("/heart/tasks", json={"goal": "test", "risk_level": "extreme"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


# ──────────────────────────────────────────────────────────────────────────────
# 3. Get Task — error paths
# ──────────────────────────────────────────────────────────────────────────────


def test_get_nonexistent_task_returns_404(client: TestClient):
    resp = client.get("/heart/tasks/nonexistent-123")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "task_not_found"
    assert resp.json()["error"]["details"]["task_id"] == "nonexistent-123"


# ──────────────────────────────────────────────────────────────────────────────
# 4. Get Events
# ──────────────────────────────────────────────────────────────────────────────


def test_get_events_for_new_task(client: TestClient):
    resp = client.post("/heart/tasks", json={"goal": "Event test"})
    task_id = resp.json()["task_id"]

    resp2 = client.get(f"/heart/tasks/{task_id}/events")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["task_id"] == task_id
    # engine.create_task emits at least one event
    assert len(data["events"]) >= 1


def test_get_events_nonexistent_task_returns_404(client: TestClient):
    resp = client.get("/heart/tasks/bad-id/events")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 5. Approve Task — requires correct state
# ──────────────────────────────────────────────────────────────────────────────


def test_approve_high_risk_task(client: TestClient, api: HeartAPI):
    """High-risk: create→intake, plan→ready_for_approval, approve→success."""
    resp = client.post("/heart/tasks", json={"goal": "Needs approval", "risk_level": "high"})
    task_id = resp.json()["task_id"]

    # Advance to ready_for_approval via plan()
    client.post(f"/heart/tasks/{task_id}/plan")  # plan is not an endpoint—use HeartAPI directly

    # Actually, the HTTP adapter doesn't expose plan(). We need to approve from the right state.
    # For high-risk, plan() stops at ready_for_approval. Let's test a different way:
    # Use the api fixture directly to prepare state, then test the HTTP endpoint.

    # We'll test approval on a task that's already in the right state.
    # api fixture is already a HeartAPI instance — use it directly.
    t = api.create_task({"goal": "HTTP approve test", "risk_level": "high"})
    tid = t["task_id"]
    api.plan(tid)
    assert api.get_task(tid)["status"] == "ready_for_approval"

    # Now test the HTTP endpoint
    resp2 = client.post(
        f"/heart/tasks/{tid}/approve",
        json={"decision": "approved", "approved_by": "alice"},
    )
    assert resp2.status_code == 200


def test_approve_missing_decision_returns_422(client: TestClient):
    resp = client.post("/heart/tasks", json={"goal": "test"})
    task_id = resp.json()["task_id"]
    resp2 = client.post(f"/heart/tasks/{task_id}/approve", json={"approved_by": "bob"})
    assert resp2.status_code == 422  # Pydantic validation


def test_approve_nonexistent_task_returns_409(client: TestClient):
    """approve_task on nonexistent task raises ApprovalRequired → 409."""
    resp = client.post(
        "/heart/tasks/bad-id/approve",
        json={"decision": "approved", "approved_by": "alice"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "approval_required"


# ──────────────────────────────────────────────────────────────────────────────
# 6. Plan Execution
# ──────────────────────────────────────────────────────────────────────────────


def _prepare_medium_approved(api: HeartAPI) -> str:
    """Helper: create, plan, and approve a medium-risk task. Returns task_id."""
    t = api.create_task({"goal": "Plan test", "risk_level": "medium"})
    tid = t["task_id"]
    api.plan(tid)
    api.approve_task(tid, {"decision": "approved", "approved_by": "test"})
    return tid


def test_plan_execution(client: TestClient, api: HeartAPI):
    tid = _prepare_medium_approved(api)
    resp = client.post(f"/heart/tasks/{tid}/plan-execution")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "evidence_gate"
    assert "task_graph" in data


def test_plan_execution_nonexistent_task_returns_404(client: TestClient):
    resp = client.post("/heart/tasks/bad-id/plan-execution")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 7. Apply Execution (dry-run)
# ──────────────────────────────────────────────────────────────────────────────


def test_apply_execution_dry_run_full_flow(client: TestClient, api: HeartAPI):
    """Medium-risk: create→plan→approve→plan_execution→apply(dry_run)→audit."""
    tid = _prepare_medium_approved(api)
    client.post(f"/heart/tasks/{tid}/plan-execution")

    # apply dry-run
    resp = client.post(
        f"/heart/tasks/{tid}/apply-execution",
        json={"dry_run": True, "provider": "fake"},
    )
    assert resp.status_code == 200

    # get audit report
    resp2 = client.get(f"/heart/tasks/{tid}/audit-report")
    assert resp2.status_code == 200
    report = resp2.json()
    assert report["status"] == "passed"
    assert len(report["events"]) > 0


def test_apply_execution_dry_run_false_rejected(client: TestClient, api: HeartAPI):
    """dry_run=False with provider=real should be rejected when feature flag is off."""
    tid = _prepare_medium_approved(api)
    client.post(f"/heart/tasks/{tid}/plan-execution")

    resp = client.post(
        f"/heart/tasks/{tid}/apply-execution",
        json={"dry_run": False, "provider": "real"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] in ("forbidden", "feature_flag_disabled")


def test_apply_execution_no_plan_returns_error(client: TestClient, api: HeartAPI):
    """apply without prior plan_execution should fail."""
    tid = _prepare_medium_approved(api)
    # Don't call plan_execution — just try to apply directly
    # First, we need to advance to evidence_gate without plan
    # Actually, we need the task in evidence_gate for apply_execution_plan to even check
    # Let's just verify that apply from wrong state returns an error

    resp = client.post(
        f"/heart/tasks/{tid}/apply-execution",
        json={"dry_run": True},
    )
    # Task is in ready_for_approval, not evidence_gate → should fail
    assert resp.status_code in (400, 409)


def test_apply_execution_nonexistent_task_returns_404(client: TestClient):
    resp = client.post(
        "/heart/tasks/bad-id/apply-execution",
        json={"dry_run": True},
    )
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 8. Advance
# ──────────────────────────────────────────────────────────────────────────────


def test_advance_from_wrong_state_returns_409(client: TestClient):
    """advance from intake should fail — not a valid transition."""
    resp = client.post("/heart/tasks", json={"goal": "Advance test"})
    task_id = resp.json()["task_id"]

    resp2 = client.post(f"/heart/tasks/{task_id}/advance")
    # intake → advance is invalid
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "invalid_transition"


def test_advance_nonexistent_task_returns_404(client: TestClient):
    resp = client.post("/heart/tasks/bad-id/advance")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 9. Audit Report
# ──────────────────────────────────────────────────────────────────────────────


def test_audit_report_no_evidence_returns_400(client: TestClient, api: HeartAPI):
    """get_audit_report before apply_execution should fail."""
    tid = _prepare_medium_approved(api)
    client.post(f"/heart/tasks/{tid}/plan-execution")
    # Don't apply → no delivery evidence

    resp = client.get(f"/heart/tasks/{tid}/audit-report")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


def test_audit_report_nonexistent_task_returns_404(client: TestClient):
    resp = client.get("/heart/tasks/bad-id/audit-report")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 10. Error format contract
# ──────────────────────────────────────────────────────────────────────────────


def test_error_response_format_404(client: TestClient):
    resp = client.get("/heart/tasks/nope-123")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "task_not_found"
    assert "message" in body["error"]
    assert "details" in body["error"]


def test_error_response_format_400(client: TestClient):
    resp = client.post("/heart/tasks", json={"goal": "x", "risk_level": "INVALID"})
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "bad_request"
