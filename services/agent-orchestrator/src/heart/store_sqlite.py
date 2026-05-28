"""SQLite-backed HeartStore for P3-B persistence.

Five tables: heart_tasks, heart_task_graphs, heart_events,
heart_approvals, heart_execution_plans.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from .models import AgentRole, EvidenceEvent, TaskGraph, TaskNode, TaskNodeStatus, TaskRun, TaskStatus, RiskLevel, now_iso


class SQLiteHeartStore:
    """Persistent SQLite store for Heart Mode runtime.

    Thread-safe via a single write lock; reads are unlocked.
    Schema is auto-created on first open.
    """

    def __init__(self, db_path: str | Path = "heart.db") -> None:
        self._path = Path(db_path)
        self._lock = threading.RLock()
        self._init_schema()

    # ── schema init ──────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS heart_tasks (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    requires_human_approval INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS heart_task_graphs (
                    task_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS heart_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    idempotency_key TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS heart_approvals (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    approved_by TEXT,
                    idempotency_key TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS heart_execution_plans (
                    task_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    idempotency_key TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS heart_delivery_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    delivery_id TEXT NOT NULL,
                    idempotency_key TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(task_id, idempotency_key)
                );
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ── TaskRun ───────────────────────────────────────────────────────────────

    def create_task(self, task: TaskRun) -> TaskRun:
        task.task_id = task.task_id or self._new_id("task")
        payload = self._task_to_payload(task)
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO heart_tasks (id, goal, status, risk_level, "
                "requires_human_approval, created_at, updated_at, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task.task_id,
                    task.goal,
                    task.status.value,
                    task.risk_level.value,
                    int(task.constraints.get("requires_human_approval", False)),
                    task.created_at,
                    task.updated_at or now_iso(),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            # save graph if present
            if task.task_graph is not None:
                self._save_graph(conn, task.task_id, task.task_graph)
        return task

    def get_task(self, task_id: str) -> Optional[TaskRun]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM heart_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def update_task(self, task: TaskRun) -> TaskRun:
        payload = self._task_to_payload(task)
        with self._lock, self._conn() as conn:
            conn.execute(
                "UPDATE heart_tasks SET goal=?, status=?, risk_level=?, "
                "requires_human_approval=?, updated_at=?, payload_json=? "
                "WHERE id=?",
                (
                    task.goal,
                    task.status.value,
                    task.risk_level.value,
                    int(task.constraints.get("requires_human_approval", False)),
                    now_iso(),
                    json.dumps(payload, ensure_ascii=False),
                    task.task_id,
                ),
            )
            if task.task_graph is not None:
                self._save_graph(conn, task.task_id, task.task_graph)
        return task

    def _task_to_payload(self, task: TaskRun) -> dict[str, Any]:
        """Serialize TaskRun minus fields stored as columns."""
        return {
            "created_by": task.created_by,
            "constraints": task.constraints,
            "team_assignment": task.team_assignment,
            "acceptance_criteria": task.acceptance_criteria,
            "delivery_report": task.delivery_report,
        }

    def _row_to_task(self, row: sqlite3.Row) -> TaskRun:
        payload = json.loads(row["payload_json"])
        # reconstruct from stored graph
        graph = self._load_graph(row["id"])
        return TaskRun(
            task_id=row["id"],
            goal=row["goal"],
            status=TaskStatus(row["status"]),
            risk_level=RiskLevel(row["risk_level"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=payload.get("created_by", "system"),
            constraints=payload.get("constraints", {}),
            task_graph=graph,
            team_assignment=payload.get("team_assignment", {}),
            acceptance_criteria=payload.get("acceptance_criteria", []),
            delivery_report=payload.get("delivery_report"),
        )

    # ── TaskGraph ─────────────────────────────────────────────────────────────

    def _save_graph(self, conn: sqlite3.Connection, task_id: str, graph: TaskGraph) -> None:
        payload = {
            "nodes": [
                {
                    "id": n.id,
                    "phase": n.phase,
                    "description": n.description,
                    "owner_agent": n.owner_agent.value,
                    "acceptance_criteria": n.acceptance_criteria,
                    "depends_on": n.depends_on,
                    "status": n.status.value,
                    "artifacts": n.artifacts,
                    "retry_count": n.retry_count,
                }
                for n in graph.nodes
            ],
            "edges": graph.edges,
            "version": graph.version,
        }
        ts = now_iso()
        conn.execute(
            "INSERT OR REPLACE INTO heart_task_graphs "
            "(task_id, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (task_id, json.dumps(payload, ensure_ascii=False), ts, ts),
        )

    def _load_graph(self, task_id: str) -> TaskGraph | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT payload_json FROM heart_task_graphs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload_json"])
        nodes = [
            TaskNode(
                id=n["id"],
                phase=n["phase"],
                description=n["description"],
                owner_agent=AgentRole(n["owner_agent"]),
                acceptance_criteria=n.get("acceptance_criteria", []),
                depends_on=n.get("depends_on", []),
                status=TaskNodeStatus(n.get("status", "pending")),
                artifacts=n.get("artifacts", []),
                retry_count=n.get("retry_count", 0),
            )
            for n in payload.get("nodes", [])
        ]
        return TaskGraph(nodes=nodes, edges=payload.get("edges", []),
                         version=payload.get("version", 1))

    # ── Events ────────────────────────────────────────────────────────────────

    def append_event(
        self,
        event: EvidenceEvent,
        idempotency_key: str | None = None,
    ) -> EvidenceEvent:
        event.event_id = event.event_id or self._new_id("evt")
        event.timestamp = event.timestamp or now_iso()
        payload = {
            "previous_state": event.previous_state,
            "new_state": event.new_state,
            "agent": event.agent,
            "data": event.data,
            "duration_ms": event.duration_ms,
            "error": event.error,
        }
        with self._lock, self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO heart_events "
                    "(id, task_id, event_type, idempotency_key, payload_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        event.event_id,
                        event.task_id,
                        event.event_type,
                        idempotency_key,
                        json.dumps(payload, ensure_ascii=False),
                        event.timestamp,
                    ),
                )
            except sqlite3.IntegrityError:
                # idempotency key conflict — fetch existing
                row = conn.execute(
                    "SELECT id FROM heart_events "
                    "WHERE task_id=? AND idempotency_key=?",
                    (event.task_id, idempotency_key),
                ).fetchone()
                if row:
                    event.event_id = row["id"]
        return event

    def get_events(self, task_id: str) -> list[EvidenceEvent]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM heart_events WHERE task_id = ? ORDER BY created_at",
                (task_id,),
            ).fetchall()
        result = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            result.append(EvidenceEvent(
                event_id=row["id"],
                task_id=row["task_id"],
                event_type=row["event_type"],
                timestamp=row["created_at"],
                agent=payload.get("agent", ""),
                previous_state=payload.get("previous_state"),
                new_state=payload.get("new_state"),
                data=payload.get("data"),
                duration_ms=payload.get("duration_ms"),
                error=payload.get("error"),
            ))
        return result

    # ── Approvals ─────────────────────────────────────────────────────────────

    def create_approval(
        self,
        task_id: str,
        decision: str,
        approved_by: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        record_id = self._new_id("apr")
        with self._lock, self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO heart_approvals "
                    "(id, task_id, decision, approved_by, idempotency_key, payload_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_id,
                        task_id,
                        decision,
                        approved_by,
                        idempotency_key,
                        json.dumps(payload, ensure_ascii=False),
                        now_iso(),
                    ),
                )
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT id FROM heart_approvals "
                    "WHERE task_id=? AND idempotency_key=?",
                    (task_id, idempotency_key),
                ).fetchone()
                if row:
                    record_id = row["id"]
        return self.get_approval_by_id(conn, record_id)

    def get_approval_by_id(self, conn: sqlite3.Connection, record_id: str) -> dict:
        row = conn.execute(
            "SELECT * FROM heart_approvals WHERE id = ?", (record_id,)
        ).fetchone()
        if not row:
            return {}
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "decision": row["decision"],
            "approved_by": row["approved_by"],
            "payload": json.loads(row["payload_json"]),
            "idempotency_key": row["idempotency_key"],
            "created_at": row["created_at"],
        }

    def get_approvals(self, task_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM heart_approvals WHERE task_id = ? ORDER BY created_at",
                (task_id,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "task_id": r["task_id"],
                "decision": r["decision"],
                "approved_by": r["approved_by"],
                "payload": json.loads(r["payload_json"]),
                "idempotency_key": r["idempotency_key"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ── Execution Plans ────────────────────────────────────────────────────────

    def save_execution_plan(
        self,
        task_id: str,
        plan_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        with self._lock, self._conn() as conn:
            # check if already exists
            existing = conn.execute(
                "SELECT * FROM heart_execution_plans WHERE task_id = ?", (task_id,)
            ).fetchone()
            if existing:
                return {
                    "task_id": existing["task_id"],
                    "plan_id": existing["plan_id"],
                    "payload": json.loads(existing["payload_json"]),
                    "idempotency_key": existing["idempotency_key"],
                    "created_at": existing["created_at"],
                    "updated_at": existing["updated_at"],
                }
            record_id = self._new_id("pln")
            ts = now_iso()
            conn.execute(
                "INSERT INTO heart_execution_plans "
                "(task_id, plan_id, idempotency_key, payload_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, plan_id, idempotency_key,
                 json.dumps(payload, ensure_ascii=False), ts, ts),
            )
            return {
                "task_id": task_id,
                "plan_id": plan_id,
                "payload": payload,
                "idempotency_key": idempotency_key,
                "created_at": ts,
                "updated_at": ts,
            }

    def get_execution_plan(self, task_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM heart_execution_plans WHERE task_id = ?", (task_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "task_id": row["task_id"],
            "plan_id": row["plan_id"],
            "payload": json.loads(row["payload_json"]),
            "idempotency_key": row["idempotency_key"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ── Delivery Evidence (P3-C) ─────────────────────────────────────────────────

    def save_delivery_evidence(
        self,
        task_id: str,
        delivery_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict:
        record_id = self._new_id("del")
        with self._lock, self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO heart_delivery_events "
                    "(id, task_id, delivery_id, idempotency_key, payload_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        record_id,
                        task_id,
                        delivery_id,
                        idempotency_key,
                        json.dumps(payload, ensure_ascii=False),
                        now_iso(),
                    ),
                )
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT id FROM heart_delivery_events "
                    "WHERE task_id=? AND idempotency_key=?",
                    (task_id, idempotency_key),
                ).fetchone()
                if row:
                    record_id = row["id"]
        return self._get_delivery_by_id(conn, record_id)

    def _get_delivery_by_id(self, conn: sqlite3.Connection, record_id: str) -> dict:
        row = conn.execute(
            "SELECT * FROM heart_delivery_events WHERE id = ?", (record_id,)
        ).fetchone()
        if not row:
            return {}
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "delivery_id": row["delivery_id"],
            "payload": json.loads(row["payload_json"]),
            "idempotency_key": row["idempotency_key"],
            "created_at": row["created_at"],
        }

    def get_delivery_evidence(self, task_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM heart_delivery_events WHERE task_id = ? ORDER BY created_at",
                (task_id,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "task_id": r["task_id"],
                "delivery_id": r["delivery_id"],
                "payload": json.loads(r["payload_json"]),
                "idempotency_key": r["idempotency_key"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _new_id(self, prefix: str) -> str:
        import uuid as _uuid
        return f"{prefix}_{_uuid.uuid4().hex[:12]}"

    # Expose for engine.py convenience methods
    def close(self) -> None:
        pass  # connection-per-call, nothing to close