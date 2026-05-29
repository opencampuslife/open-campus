"""HeartAPI — Python internal adapter for Heart Mode runtime.

Not an HTTP server. Provides a stable, type-safe call interface that
the Go control-plane can proxy to once P2-B+ adds HTTP routing.

P2-B scope: create_task / get_task / get_events / approve_task / cancel_task.
Out of scope (P2-B): execute_task, create_pr, run_ci, deploy, merge.
"""

from __future__ import annotations

import uuid

from .approval import ApprovalGate, ApprovalRequest
from .engine import HeartEngine
from .errors import (
    ApprovalRejected,
    ApprovalRequired,
    EvidenceGateFailed,
    InvalidTransition,
    TaskAlreadyTerminal,
    TaskNotFound,
)
from .evidence_gate import EvidenceGate, GateDecision
from .models import RiskLevel, TaskRun, TaskStatus, now_iso
from .policies import requires_approval
from .providers import (
    FileChange,
    GitHubProviderConfig,
    select_git_provider,
)
from .safety_events import (
    build_branch_created,
    build_commit_created,
    build_pr_opened,
    build_provider_selected,
    build_write_guard_blocked,
    build_write_guard_passed,
)
from .audit import report_from_delivery_evidence
from .store import HeartStore
from .write_guard import WriteGuard, WriteGuardResult


# ── Response helpers ────────────────────────────────────────────────────────

def _task_to_dict(task: TaskRun) -> dict:
    """Serialize TaskRun to contract-compatible dict."""
    return {
        "task_id": task.task_id,
        "goal": task.goal,
        "risk_level": task.risk_level.value,
        "status": task.status.value,
        "created_at": task.created_at,
        "updated_at": task.updated_at or "",
        "created_by": task.created_by,
        "constraints": task.constraints,
        "acceptance_criteria": task.acceptance_criteria,
        "team_assignment": task.team_assignment,
        "task_graph": _graph_to_dict(task.task_graph) if task.task_graph else None,
        "delivery_report": task.delivery_report,
    }


def _graph_to_dict(graph) -> dict | None:
    if graph is None:
        return None
    return {
        "node_count": graph.node_count,
        "nodes": [
            {
                "id": n.id,
                "phase": n.phase,
                "description": n.description,
                "owner_agent": n.owner_agent.value,
                "depends_on": n.depends_on,
                "acceptance_criteria": n.acceptance_criteria,
                "status": n.status.value,
            }
            for n in graph.nodes
        ],
        "edges": graph.edges,
    }


def _events_to_dict(task_id: str, events) -> dict:
    return {
        "task_id": task_id,
        "events": [
            {
                "event_id": e.event_id,
                "task_id": e.task_id,
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "agent": e.agent,
                "previous_state": e.previous_state or "",
                "new_state": e.new_state or "",
                "data": e.data or {},
                "error": e.error or "",
            }
            for e in events
        ],
    }


# ── HeartAPI ───────────────────────────────────────────────────────────────


class HeartAPI:
    """Stable Python call interface for Heart Mode.

    Wraps HeartEngine + ApprovalGate + EvidenceGate into a single
    high-level API. Designed to be called from:
        - Go control-plane via subprocess or gRPC
        - Admin Console via REST (future)
        - Test fixtures
    """

    def __init__(self, store: HeartStore | None = None) -> None:
        self._engine = HeartEngine(store=store)
        self._approval = ApprovalGate(store=self._engine.store)
        self._evidence = EvidenceGate(store=self._engine.store)
        self._guard = WriteGuard()
        # P3-D: GitHub config (defaults off — must be explicitly enabled)
        self._github_config = GitHubProviderConfig()

    def create_task(self, request: dict) -> dict:
        """Create a task and advance through intake.

        Args:
            request: {
                "goal": str (required),
                "risk_level": str ("low"|"medium"|"high"|"critical"), default "low",
                "created_by": str, default "system",
                "acceptance_criteria": list[str],
                "requires_human_approval": bool|null,
            }

        Returns:
            TaskRun dict matching heart-task.schema.json
        """
        goal = request.get("goal")
        if not goal:
            raise ValueError("goal is required")

        risk_level = request.get("risk_level", "low")
        try:
            RiskLevel(risk_level)
        except ValueError:
            raise ValueError(f"invalid risk_level: {risk_level}")

        task = self._engine.create_task(
            goal=goal,
            risk_level=risk_level,
            created_by=request.get("created_by", "system"),
            acceptance_criteria=request.get("acceptance_criteria"),
            requires_human_approval=request.get("requires_human_approval"),
        )
        return _task_to_dict(task)

    def get_task(self, task_id: str) -> dict:
        """Get task by ID. Raises TaskNotFound if not found."""
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)
        return _task_to_dict(task)

    def get_events(self, task_id: str) -> dict:
        """Get all evidence events for a task."""
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)
        return _events_to_dict(task_id, self._engine.get_events(task_id))

    def approve_task(self, task_id: str, request: dict) -> dict:
        """Approve or reject a task.

        Args:
            request: {
                "decision": "approved"|"rejected"|"modified",
                "approved_by": str (required),
                "reason": str,
                "modifications": list[str],
            }

        Returns: updated TaskRun dict.
        """
        decision = request.get("decision")
        if decision not in {"approved", "rejected", "modified"}:
            raise ValueError(f"invalid decision: {decision}")

        approved_by = request.get("approved_by")
        if not approved_by:
            raise ValueError("approved_by is required")

        ar = ApprovalRequest(
            decision=decision,
            approved_by=approved_by,
            reason=request.get("reason"),
            modifications=request.get("modifications", []),
            idempotency_key=f"approval_{task_id}_{decision}",
        )

        if decision == "rejected":
            task = self._approval.reject(task_id, ar)
        else:
            task = self._approval.grant(task_id, ar)

        return _task_to_dict(task)

    def cancel_task(
        self,
        task_id: str,
        request: dict | None = None,
    ) -> dict:
        """Cancel a task from any non-terminal state."""
        cancelled_by = "system"
        reason = None
        if request:
            cancelled_by = request.get("cancelled_by", "system")
            reason = request.get("reason")

        task = self._approval.cancel(task_id, cancelled_by, reason)
        return _task_to_dict(task)

    def evaluate_gate(self, task_id: str) -> GateDecision:
        """Run EvidenceGate structural checks."""
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)
        return self._evidence.evaluate(task_id)

    # ── convenience ────────────────────────────────────────────────────

    def plan(self, task_id: str) -> dict:
        """Run planning pipeline (intake → planning → team_formation)."""
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)
        task = self._engine.plan(task_id)
        return _task_to_dict(task)

    def advance(self, task_id: str) -> dict:
        """Advance task past the execution stage (execution→evidence_gate or evidence_gate→completed).

        Does NOT handle ready_for_approval→execution — use plan_execution() for that.
        """
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)

        if task.status == TaskStatus.EXECUTION:
            # execution is done; advance to evidence_gate
            task = self._engine.complete_execution(task_id)
            return _task_to_dict(task)

        if task.status == TaskStatus.EVIDENCE_GATE:
            # evidence_gate is done; advance to completed
            task = self._engine.complete_gate(task_id)
            return _task_to_dict(task)

        raise InvalidTransition(
            task_id, task.status.value, "advance",
            f"cannot advance from {task.status.value} — only execution or evidence_gate allowed",
        )

    def plan_execution(self, task_id: str) -> dict:
        """Run ExecutorAgent to generate ExecutionPlan for an approved task.

        P3-A: dry-run only. No real GitHub write. No CI run.
        Preconditions: task in execution state, approval_granted event exists.
        """
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)

        task = self._engine.plan_execution(task_id)
        return _task_to_dict(task)

    def apply_execution_plan(self, task_id: str, request: dict | None = None) -> dict:
        """Apply a generated ExecutionPlan — creates branch, commits files, opens PR.

        P3-C/P3-D scope: controlled GitHub write.
        - Allowed: create_branch, commit_files, open_pr, get_commit_status
        - Forbidden: merge, delete_branch, push_main, force_push, modify_secrets/auth/deploy

        P3-C (default): dry_run=True, provider=fake, no feature flag needed.
        P3-D: dry_run=False + provider=real requires HEART_GITHUB_WRITE_ENABLED=1.

        State boundary (P3-C locked):
            apply_execution_plan(): evidence_gate → evidence_gate (no status change)
            advance(): evidence_gate → completed

        Args:
            request: {
                "dry_run": bool,       default True
                "provider": str,       default "fake"  ("fake" | "real")
                "branch_name": str,   optional, auto-generated if missing
            }

        Returns:
            TaskRun dict (status unchanged — use advance() to reach completed).
        """
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)

        request = request or {}
        dry_run = request.get("dry_run", True)
        provider = request.get("provider", "fake")

        # ── P3-E: collect safety events ────────────────────────────────────────
        safety_events: list[dict] = []

        # ── preconditions: task state ──────────────────────────────────────────
        if task.status == TaskStatus.COMPLETED:
            return _task_to_dict(task)  # idempotent

        if task.status != TaskStatus.EVIDENCE_GATE:
            raise InvalidTransition(
                task_id, task.status.value, "apply_execution_plan",
                "apply_execution_plan requires task in evidence_gate state",
            )

        # ── preconditions: plan exists ───────────────────────────────────────
        plan = self._engine.store.get_execution_plan(task_id)
        if plan is None:
            raise ValueError(f"no execution plan found for task {task_id}")

        # ── P3-D: dry_run=False requires provider=real AND feature flag ───────
        flag_checked = False
        flag_enabled = False
        if not dry_run:
            if provider != "real":
                raise ValueError(
                    "dry_run=False requires provider='real'. "
                    "Use provider='fake' for dry-run, or enable real GitHub writes.",
                )
            # selector raises FeatureFlagDisabled if flag is off
            _ = select_git_provider(self._github_config, "real")
            flag_checked = True
            flag_enabled = True

        # ── P3-E: provider_selected event ─────────────────────────────────────
        safety_events.append(build_provider_selected(
            provider=provider,
            dry_run=dry_run,
            feature_flag_checked=flag_checked,
            feature_flag_enabled=flag_enabled,
            repo=self._github_config.github_repo,
        ).to_dict())

        # ── preconditions: approval ───────────────────────────────────────────
        approvals = self._engine.store.get_approvals(task_id)
        has_approval = any(a.get("decision") in {"approved", "modified"} for a in approvals)
        guard_result = self._guard.check_all(
            risk_level=task.risk_level.value,
            has_approval=has_approval,
            has_plan=True,
        )
        if not guard_result.allowed:
            # ── P3-E: write_guard_blocked event ─────────────────────────────
            safety_events.append(build_write_guard_blocked(
                provider=provider,
                dry_run=dry_run,
                reason_code=guard_result.code,
                target_branch=request.get("branch_name", ""),
                repo=self._github_config.github_repo,
            ).to_dict())
            # persist events before raising
            self._persist_with_safety_events(task_id, safety_events, provider, dry_run)
            raise PermissionError(
                f"apply_execution_plan blocked: {guard_result.code} — {guard_result.reason}",
            )

        # ── extract plan steps ───────────────────────────────────────────────
        steps = plan.get("payload", {}).get("steps", [])
        if not steps:
            raise ValueError(f"execution plan for task {task_id} has no steps")

        # ── collect file operations from plan steps ──────────────────────────
        changes: list[FileChange] = []
        for step in steps:
            tool_name = step.get("tool_name", "")
            if tool_name not in {"write_files", "modify_files", "create_branch"}:
                continue
            inp = step.get("input", {})
            paths = inp.get("paths", [])
            contents = inp.get("contents", [])
            if isinstance(paths, str):
                paths = [paths]
            if isinstance(contents, str):
                contents = [contents]

            for i, path in enumerate(paths):
                content = contents[i] if i < len(contents) else b""
                if isinstance(content, str):
                    content = content.encode("utf-8")
                changes.append(FileChange(path=path, content=content))

        # ── build branch name ─────────────────────────────────────────────────
        branch_name = request.get("branch_name")
        if not branch_name:
            short_id = uuid.uuid4().hex[:8]
            safe_goal = "".join(c if c.isalnum() or c in "-_" else "-" for c in task.goal)
            branch_name = f"heart/{safe_goal[:30]}-{short_id}"

        # ── WriteGuard checks on branch and paths ────────────────────────────
        guard_result = self._guard.check_all(
            branch=branch_name,
            paths=[c.path for c in changes],
            operation="commit_files",
        )
        if not guard_result.allowed:
            # ── P3-E: write_guard_blocked event ─────────────────────────────
            safety_events.append(build_write_guard_blocked(
                provider=provider,
                dry_run=dry_run,
                reason_code=guard_result.code,
                target_branch=branch_name,
                blocked_paths=[c.path for c in changes],
                repo=self._github_config.github_repo,
            ).to_dict())
            self._persist_with_safety_events(task_id, safety_events, provider, dry_run)
            raise PermissionError(
                f"apply_execution_plan blocked: {guard_result.code} — {guard_result.reason}",
            )

        # ── P3-E: write_guard_passed event ──────────────────────────────────
        safety_events.append(build_write_guard_passed(
            provider=provider,
            dry_run=dry_run,
            target_branch=branch_name,
            operation_count=len(changes),
            file_count=len(changes),
            risk_level=task.risk_level.value,
            repo=self._github_config.github_repo,
        ).to_dict())

        # ── execute via selected provider ────────────────────────────────────
        git = select_git_provider(self._github_config, provider)

        br_result = None
        commit_result = None
        pr_result = None

        if dry_run:
            delivery_id = f"dry_run_{task_id}"
            # P3-E: emit simulated events so audit trail is complete in dry-run too
            safety_events.append(build_branch_created(
                provider=provider,
                dry_run=True,
                branch=branch_name,
                base_branch="main",
                repo=self._github_config.github_repo,
            ).to_dict())
            safety_events.append(build_commit_created(
                provider=provider,
                dry_run=True,
                branch=branch_name,
                commit_sha=f"dry_run_sha_{uuid.uuid4().hex[:8]}",
                file_count=len(changes),
                repo=self._github_config.github_repo,
            ).to_dict())
            pr_number = int(f"1{uuid.uuid4().hex[:6]}", 16) % 10000 + 1
            safety_events.append(build_pr_opened(
                provider=provider,
                dry_run=True,
                branch=branch_name,
                base_branch="main",
                pr_number=pr_number,
                pr_url=f"https://github.com/{self._github_config.github_owner}/{self._github_config.github_repo}/pull/{pr_number}",
                title=f"[DRY-RUN] Heart Mode: {task.goal[:60]}",
                repo=self._github_config.github_repo,
            ).to_dict())
            payload = {
                "dry_run": True,
                "provider": provider,
                "branch": branch_name,
                "files": [c.path for c in changes],
                "file_count": len(changes),
                "note": "P3-C dry-run: no real GitHub API calls",
            }
        else:
            br_result = git.create_branch(branch_name)
            commit_result = git.commit_files(branch_name, changes)
            pr_result = git.open_pr(
                branch_name,
                title=f"Heart Mode: {task.goal[:60]}",
                body=self._build_pr_body(task, steps),
            )
            delivery_id = commit_result.data.get("commit_sha") or f"pr_{br_result.data.get('branch', '')}"

            # ── P3-E: branch_created event ──────────────────────────────────
            safety_events.append(build_branch_created(
                provider=provider,
                dry_run=False,
                branch=branch_name,
                base_branch=br_result.data.get("base", "main"),
                repo=self._github_config.github_repo,
            ).to_dict())

            # ── P3-E: commit_created event ──────────────────────────────────
            if commit_result.success:
                safety_events.append(build_commit_created(
                    provider=provider,
                    dry_run=False,
                    branch=branch_name,
                    commit_sha=commit_result.data.get("commit_sha", ""),
                    file_count=len(changes),
                    repo=self._github_config.github_repo,
                ).to_dict())

            # ── P3-E: pr_opened event ──────────────────────────────────────
            if pr_result.success:
                safety_events.append(build_pr_opened(
                    provider=provider,
                    dry_run=False,
                    branch=branch_name,
                    base_branch=pr_result.data.get("base_branch", "main"),
                    pr_number=pr_result.data.get("pr_number", 0),
                    pr_url=pr_result.data.get("url", ""),
                    title=pr_result.data.get("title", ""),
                    repo=self._github_config.github_repo,
                ).to_dict())

            payload = {
                "dry_run": False,
                "provider": provider,
                "branch": branch_name,
                "commit_sha": commit_result.data.get("commit_sha"),
                "pr_url": pr_result.data.get("url"),
                "pr_number": pr_result.data.get("pr_number"),
                "files": [c.path for c in changes],
                "file_count": len(changes),
                "git_results": {
                    "create_branch": br_result.to_dict(),
                    "commit_files": commit_result.to_dict(),
                    "open_pr": pr_result.to_dict(),
                },
            }

        # ── persist delivery evidence with safety events ────────────────────
        payload["safety_events"] = safety_events
        idempotency_key = f"delivery_{task_id}"
        self._engine.store.save_delivery_evidence(
            task_id=task_id,
            delivery_id=delivery_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )

        # refresh task from store
        task = self._engine.get_task(task_id)
        return _task_to_dict(task)

    def _build_pr_body(self, task: TaskRun, steps: list[dict]) -> str:
        """Build PR description from task and plan steps."""
        lines = [
            f"## Task: {task.goal}",
            f"**Risk Level:** {task.risk_level.value}",
            "",
            "### Execution Steps",
        ]
        for step in steps:
            lines.append(f"- [{step.get('status', '?')}] {step.get('title', '')} "
                         f"(`{step.get('tool_name', '')}`)")
        lines.append("")
        lines.append("---")
        lines.append("*Generated by Heart Mode — P3-D*")
        return "\n".join(lines)

    # ── P3-E: Safety event persistence ──────────────────────────────────────

    def _persist_with_safety_events(
        self,
        task_id: str,
        safety_events: list[dict],
        provider: str,
        dry_run: bool,
    ) -> None:
        """Persist delivery evidence with safety events when blocked.

        Called when WriteGuard blocks the operation — no provider was called,
        so we persist just the events and the blocked status.
        """
        delivery_id = f"blocked_{task_id}"
        payload = {
            "dry_run": dry_run,
            "provider": provider,
            "blocked": True,
            "safety_events": safety_events,
        }
        idempotency_key = f"delivery_{task_id}"
        self._engine.store.save_delivery_evidence(
            task_id=task_id,
            delivery_id=delivery_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    # ── P3-E: Audit report ───────────────────────────────────────────────────

    def get_audit_report(self, task_id: str) -> dict:
        """Build and return an AuditReport for a task.

        Assembles from delivery_evidence stored in the events table.
        Does NOT change any task status.

        Args:
            task_id: the task to generate a report for.

        Returns:
            AuditReport dict matching P3-E event protocol.

        Raises:
            TaskNotFound: if no task exists.
            ValueError: if no delivery evidence found for task.
        """
        task = self._engine.get_task(task_id)
        if task is None:
            raise TaskNotFound(task_id)

        # Get the latest delivery evidence
        evidence_list = self._engine.store.get_delivery_evidence(task_id)
        if not evidence_list:
            raise ValueError(f"no delivery evidence found for task {task_id}")

        # Use the latest evidence record
        evidence = evidence_list[-1] if isinstance(evidence_list, list) else evidence_list
        report = report_from_delivery_evidence(evidence)
        return report.to_dict()
