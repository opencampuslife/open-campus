"""P4-A: SQLite recovery tests.

Verify that tasks, events, and audit reports survive app restart.
Uses temp SQLite files — no persistent state left behind.

Note: The HTTP adapter does not expose plan() (out of P4-A scope).
For complex flows (medium-risk → evidence_gate), we prepare state
using HeartAPI directly, then test HTTP recovery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from heart.api import HeartAPI
from heart.service import create_app
from heart.service_config import HeartServiceConfig
from heart.store_sqlite import SQLiteHeartStore


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Temporary SQLite database path."""
    return tmp_path / "heart_recovery.sqlite3"


@pytest.fixture
def service_config(temp_db: Path) -> HeartServiceConfig:
    """Config pointing to temp SQLite."""
    return HeartServiceConfig(
        store_type="sqlite",
        db_path=temp_db,
        github_provider="fake",
        github_write_enabled=False,
    )


def _prepare_medium_approved(config: HeartServiceConfig, task_id: str) -> None:
    """Plan + approve a medium-risk task using the same SQLite store."""
    store = SQLiteHeartStore(str(config.db_path))
    api = HeartAPI(store)
    api.plan(task_id)
    api.approve_task(task_id, {"decision": "approved", "approved_by": "test"})


def _prepare_medium_to_apply(config: HeartServiceConfig, task_id: str) -> None:
    """Full flow: plan → approve → plan_execution using same SQLite store."""
    store = SQLiteHeartStore(str(config.db_path))
    api = HeartAPI(store)
    api.plan(task_id)
    api.approve_task(task_id, {"decision": "approved", "approved_by": "test"})
    api.plan_execution(task_id)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Task survives app restart
# ──────────────────────────────────────────────────────────────────────────────


def test_task_survives_recovery(service_config: HeartServiceConfig):
    """Create a task, restart the app, and verify it can be read back."""
    app1 = create_app(config=service_config)
    client1 = TestClient(app1)

    resp = client1.post("/heart/tasks", json={"goal": "Recovery test", "risk_level": "low"})
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    app2 = create_app(config=service_config)
    client2 = TestClient(app2)

    resp2 = client2.get(f"/heart/tasks/{task_id}")
    assert resp2.status_code == 200
    assert resp2.json()["task_id"] == task_id
    assert resp2.json()["goal"] == "Recovery test"


# ──────────────────────────────────────────────────────────────────────────────
# 2. Events survive app restart
# ──────────────────────────────────────────────────────────────────────────────


def test_events_survive_recovery(service_config: HeartServiceConfig):
    """Create a task, verify events persist across app instances."""
    app1 = create_app(config=service_config)
    client1 = TestClient(app1)

    resp = client1.post("/heart/tasks", json={"goal": "Events recovery"})
    task_id = resp.json()["task_id"]

    ev1 = client1.get(f"/heart/tasks/{task_id}/events")
    assert ev1.status_code == 200
    event_count = len(ev1.json()["events"])

    app2 = create_app(config=service_config)
    client2 = TestClient(app2)

    ev2 = client2.get(f"/heart/tasks/{task_id}/events")
    assert ev2.status_code == 200
    assert len(ev2.json()["events"]) == event_count


# ──────────────────────────────────────────────────────────────────────────────
# 3. Audit report survives app restart
# ──────────────────────────────────────────────────────────────────────────────


def test_audit_report_survives_recovery(service_config: HeartServiceConfig):
    """Full flow with audit report survives app restart.

    Uses HeartAPI directly to prepare state (plan, approve, plan_execution)
    since the HTTP adapter doesn't expose plan(). Then applies via HTTP
    and verifies audit report persistence across instances.
    """
    # First, create task via HTTP
    app1 = create_app(config=service_config)
    client1 = TestClient(app1)

    resp = client1.post(
        "/heart/tasks",
        json={"goal": "Audit recovery test", "risk_level": "medium"},
    )
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    # Prepare state via HeartAPI (plan → approve → plan_execution)
    _prepare_medium_to_apply(service_config, task_id)

    # Apply via HTTP (dry-run) to generate delivery evidence
    resp2 = client1.post(
        f"/heart/tasks/{task_id}/apply-execution",
        json={"dry_run": True, "provider": "fake"},
    )
    assert resp2.status_code == 200

    # Get audit report from first instance
    ar1 = client1.get(f"/heart/tasks/{task_id}/audit-report")
    assert ar1.status_code == 200

    # Restart app
    app2 = create_app(config=service_config)
    client2 = TestClient(app2)

    # Audit report should survive (except generated_at which differs by time)
    ar2 = client2.get(f"/heart/tasks/{task_id}/audit-report")
    assert ar2.status_code == 200
    ar2_data = ar2.json()
    ar1_data = ar1.json()
    # Remove timestamps before comparing
    del ar1_data["generated_at"]
    del ar2_data["generated_at"]
    assert ar2_data == ar1_data


# ──────────────────────────────────────────────────────────────────────────────
# 4. Multiple tasks survive recovery
# ──────────────────────────────────────────────────────────────────────────────


def test_multiple_tasks_survive_recovery(service_config: HeartServiceConfig):
    """Multiple tasks created in one instance should all be visible after restart."""
    app1 = create_app(config=service_config)
    client1 = TestClient(app1)

    ids = []
    for i in range(3):
        resp = client1.post(
            "/heart/tasks",
            json={"goal": f"Task {i}", "risk_level": "low"},
        )
        assert resp.status_code == 200
        ids.append(resp.json()["task_id"])

    app2 = create_app(config=service_config)
    client2 = TestClient(app2)

    for task_id in ids:
        resp = client2.get(f"/heart/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["task_id"] == task_id


# ──────────────────────────────────────────────────────────────────────────────
# 5. Empty DB survives restart (no crash)
# ──────────────────────────────────────────────────────────────────────────────


def test_empty_db_survives_restart(service_config: HeartServiceConfig):
    """App starts cleanly with empty database."""
    app1 = create_app(config=service_config)
    client1 = TestClient(app1)
    assert client1.get("/healthz").status_code == 200

    app2 = create_app(config=service_config)
    client2 = TestClient(app2)
    assert client2.get("/healthz").status_code == 200
