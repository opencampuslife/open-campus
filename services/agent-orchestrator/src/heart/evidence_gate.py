"""EvidenceGate — minimum structural integrity gate.

P2-B scope: structural checks only. No real CI verification. No LLM judgment.
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import EventType
from .models import TaskRun, now_iso
from .store import HeartStore


@dataclass
class GateCheck:
    name: str
    status: str          # "pass" | "fail" | "skip"
    detail: str | None = None


@dataclass
class GateDecision:
    status: str                           # "pass" | "blocked" | "needs_human_review"
    checks: list[GateCheck]
    blocking_issues: list[str]            # non-empty when status != pass
    task_id: str
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = now_iso()


class EvidenceGate:
    """Structural integrity gate for task delivery.

    Evaluates:
        1. task exists
        2. task graph exists
        3. team assembled (team_assignment non-empty)
        4. acceptance criteria exists
        5. approval exists if required
        6. no blocking risk (not critical-risk)
    """

    def __init__(self, store: HeartStore) -> None:
        self._store = store

    def evaluate(self, task_id: str) -> GateDecision:
        """Run all structural checks and return a GateDecision."""
        task = self._store.get_task(task_id)
        checks: list[GateCheck] = []
        issues: list[str] = []

        # ── 1. task exists ─────────────────────────────────────────────
        if task is None:
            checks.append(GateCheck(name="task_exists", status="fail", detail="task not found"))
            issues.append("task_not_found")
            return GateDecision(
                status="blocked", checks=checks, blocking_issues=issues, task_id=task_id,
            )

        checks.append(GateCheck(name="task_exists", status="pass"))

        # ── 2. task graph exists ────────────────────────────────────────
        if task.task_graph is None:
            checks.append(GateCheck(name="task_graph_exists", status="fail",
                                    detail="no plan has been generated"))
            issues.append("no_task_graph")
        else:
            checks.append(GateCheck(name="task_graph_exists", status="pass",
                                    detail=f"{task.task_graph.node_count} nodes"))

        # ── 3. team assembled ───────────────────────────────────────────
        if not task.team_assignment:
            checks.append(GateCheck(name="team_assembled", status="fail",
                                    detail="no agent team assigned"))
            issues.append("no_team_assembled")
        else:
            checks.append(GateCheck(name="team_assembled", status="pass",
                                    detail=str(list(task.team_assignment.keys()))))

        # ── 4. acceptance criteria — pass if field exists (empty is ok) ──
        # acceptance_criteria is a list; absence means undefined (blocked),
        # but [] is a valid empty acceptance list (allowed).
        if task.acceptance_criteria is None:
            checks.append(GateCheck(name="acceptance_criteria_present", status="fail",
                                    detail="no acceptance criteria defined"))
            issues.append("no_acceptance_criteria")
        else:
            checks.append(GateCheck(name="acceptance_criteria_present", status="pass",
                                    detail=f"{len(task.acceptance_criteria)} criteria"))

        # ── 5. approval exists if required ──────────────────────────────
        from .policies import requires_approval
        if requires_approval(task.risk_level):
            events = self._store.get_events(task_id)
            approval_events = {
                EventType.APPROVAL_GRANTED.value,
                EventType.APPROVAL_REJECTED.value,
            }
            has_approval = any(e.event_type in approval_events for e in events)
            if not has_approval:
                checks.append(GateCheck(name="approval_satisfied", status="fail",
                                        detail="approval required but not yet granted"))
                issues.append("missing_approval")
            else:
                checks.append(GateCheck(name="approval_satisfied", status="pass"))
        else:
            checks.append(GateCheck(name="approval_satisfied", status="skip",
                                    detail="approval not required for low-risk task"))

        # ── 6. no blocking risk ────────────────────────────────────────
        from .models import RiskLevel
        if task.risk_level == RiskLevel.CRITICAL:
            checks.append(GateCheck(name="no_blocking_risk", status="fail",
                                    detail="critical risk tasks are not eligible for automated delivery"))
            issues.append("critical_risk_blocked")
        else:
            checks.append(GateCheck(name="no_blocking_risk", status="pass"))

        # ── decision ───────────────────────────────────────────────────
        if issues:
            status = "needs_human_review" if len(issues) == 1 and issues[0] == "missing_approval" else "blocked"
        else:
            status = "pass"

        return GateDecision(
            status=status,
            checks=checks,
            blocking_issues=issues,
            task_id=task_id,
        )