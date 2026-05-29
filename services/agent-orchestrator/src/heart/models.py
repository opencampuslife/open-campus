"""Heart Mode data models — derived from contracts/schemas/heart-*.schema.json.

P2-A scope: dataclass-only, zero external deps. No LLM, no GitHub, no CI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── Enums ────────────────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """P2-A-visible states (up to ready_for_approval).
    
    Full set includes execution/review/repair/gate/completed/failed/cancelled,
    but P2-A only auto-advances through ready_for_approval.
    """
    TASK_CREATED = "task_created"
    INTAKE = "intake"
    PLANNING = "planning"
    TEAM_FORMATION = "team_formation"
    READY_FOR_APPROVAL = "ready_for_approval"
    # ── reserved for P2-B+ ──
    EXECUTION = "execution"
    REVIEW = "review"
    REPAIR = "repair"
    EVIDENCE_GATE = "evidence_gate"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskNodeStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class AgentRole(str, Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    ENGINEER = "engineer"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    REPORTER = "reporter"


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class TaskNode:
    """Single node in the task DAG."""
    id: str                                    # "tn_<slug>"
    phase: int                                 # 1-based
    description: str
    owner_agent: AgentRole
    acceptance_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: TaskNodeStatus = TaskNodeStatus.PENDING
    artifacts: list[dict[str, str]] = field(default_factory=list)
    retry_count: int = 0


@dataclass
class TaskGraph:
    """Task DAG: nodes + edges."""
    nodes: list[TaskNode] = field(default_factory=list)
    edges: list[dict[str, str]] = field(default_factory=list)
    version: int = 1

    @property
    def node_count(self) -> int:
        return len(self.nodes)


@dataclass
class AgentPermission:
    """Permission set for one agent role."""
    read_repo: bool = False
    read_evidence: bool = False
    llm: bool = False
    rag: bool = False
    write_repo: bool = False
    create_pr: bool = False
    merge_main: bool = False


# ── Permission presets (matches docs/heart-mode/agent-roles.md) ─────

AGENT_PERMISSIONS: dict[AgentRole, AgentPermission] = {
    AgentRole.PLANNER: AgentPermission(read_repo=True, llm=True, rag=True),
    AgentRole.RESEARCHER: AgentPermission(read_repo=True, read_evidence=True, rag=True),
    AgentRole.ENGINEER: AgentPermission(read_repo=True, llm=True),
    AgentRole.EXECUTOR: AgentPermission(read_repo=True, read_evidence=True),
    AgentRole.REVIEWER: AgentPermission(read_repo=True, read_evidence=True, llm=True),
    AgentRole.REPORTER: AgentPermission(read_evidence=True),
}


@dataclass
class EvidenceEvent:
    """Audit-trail event corresponding to heart-event.schema.json."""
    event_id: str                             # "evt_<random>"
    task_id: str
    event_type: str                           # EventType enum value
    timestamp: str                            # ISO-8601
    agent: str                                # AgentRole | "heart_engine"
    previous_state: str | None = None
    new_state: str | None = None
    data: dict[str, Any] | None = None
    duration_ms: int | None = None
    error: str | None = None
    # P3-B: optional idempotency key for deduplication
    idempotency_key: str | None = None


@dataclass
class TaskRun:
    """Top-level task run — matches heart-task.schema.json."""
    task_id: str
    goal: str
    risk_level: RiskLevel
    status: TaskStatus = TaskStatus.TASK_CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str | None = None
    created_by: str = "system"
    constraints: dict[str, Any] = field(default_factory=dict)
    task_graph: TaskGraph | None = None
    team_assignment: dict[str, list[str]] = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    delivery_report: dict[str, Any] | None = None

    def update_status(self, new: TaskStatus) -> None:
        self.status = new
        self.updated_at = datetime.now(timezone.utc).isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
