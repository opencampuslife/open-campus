"""Unit tests for Heart Mode models and policies."""

from __future__ import annotations

import pytest

from heart.models import (
    AgentPermission,
    AgentRole,
    RiskLevel,
    TaskNode,
    TaskNodeStatus,
    TaskRun,
    TaskStatus,
    AGENT_PERMISSIONS,
)
from heart.policies import (
    allowed_next_states,
    is_valid_transition,
    requires_approval,
    risk_blocked_state,
)


class TestRiskLevel:
    def test_low_no_approval(self):
        assert not requires_approval(RiskLevel.LOW)

    def test_medium_requires_approval(self):
        assert requires_approval(RiskLevel.MEDIUM)

    def test_high_requires_approval(self):
        assert requires_approval(RiskLevel.HIGH)

    def test_critical_requires_approval(self):
        assert requires_approval(RiskLevel.CRITICAL)

    def test_risk_blocked_critical(self):
        assert risk_blocked_state(RiskLevel.CRITICAL) == TaskStatus.BLOCKED

    def test_risk_blocked_medium(self):
        assert risk_blocked_state(RiskLevel.MEDIUM) == TaskStatus.READY_FOR_APPROVAL


class TestTransitions:
    def test_task_created_to_intake(self):
        assert is_valid_transition(TaskStatus.TASK_CREATED, TaskStatus.INTAKE)

    def test_intake_to_planning(self):
        assert is_valid_transition(TaskStatus.INTAKE, TaskStatus.PLANNING)

    def test_planning_to_team_formation(self):
        assert is_valid_transition(TaskStatus.PLANNING, TaskStatus.TEAM_FORMATION)

    def test_team_formation_to_ready_for_approval(self):
        assert is_valid_transition(TaskStatus.TEAM_FORMATION, TaskStatus.READY_FOR_APPROVAL)

    def test_ready_for_approval_no_next(self):
        # P2-B adds execution and cancelled transitions from ready_for_approval
        assert TaskStatus.EXECUTION in allowed_next_states(TaskStatus.READY_FOR_APPROVAL)
        assert TaskStatus.BLOCKED in allowed_next_states(TaskStatus.READY_FOR_APPROVAL)
        assert TaskStatus.CANCELLED in allowed_next_states(TaskStatus.READY_FOR_APPROVAL)

    def test_cannot_jump_states(self):
        assert not is_valid_transition(TaskStatus.TASK_CREATED, TaskStatus.PLANNING)

    def test_cannot_reverse(self):
        assert not is_valid_transition(TaskStatus.PLANNING, TaskStatus.INTAKE)

    def test_blocked_from_intake(self):
        assert is_valid_transition(TaskStatus.INTAKE, TaskStatus.BLOCKED)

    def test_failed_from_planning(self):
        assert is_valid_transition(TaskStatus.PLANNING, TaskStatus.FAILED)


class TestTaskRun:
    def test_default_state(self):
        task = TaskRun(task_id="task_001", goal="test", risk_level=RiskLevel.LOW)
        assert task.status == TaskStatus.TASK_CREATED
        assert task.created_by == "system"

    def test_update_status(self):
        task = TaskRun(task_id="task_001", goal="test", risk_level=RiskLevel.LOW)
        task.update_status(TaskStatus.INTAKE)
        assert task.status == TaskStatus.INTAKE
        assert task.updated_at is not None


class TestTaskNode:
    def test_minimal(self):
        node = TaskNode(
            id="tn_01", phase=1, description="Analyze", owner_agent=AgentRole.PLANNER,
        )
        assert node.status == TaskNodeStatus.PENDING
        assert node.depends_on == []
        assert node.acceptance_criteria == []
        assert node.retry_count == 0

    def test_with_deps(self):
        node = TaskNode(
            id="tn_02", phase=2, description="Implement",
            owner_agent=AgentRole.ENGINEER,
            depends_on=["tn_01"],
            acceptance_criteria=["Tests pass", "No regressions"],
        )
        assert len(node.depends_on) == 1
        assert len(node.acceptance_criteria) == 2


class TestPermissions:
    def test_planner_read_only(self):
        p = AGENT_PERMISSIONS[AgentRole.PLANNER]
        assert p.read_repo
        assert not p.write_repo
        assert not p.merge_main

    def test_executor_no_merge(self):
        p = AGENT_PERMISSIONS[AgentRole.EXECUTOR]
        assert not p.merge_main  # hard constraint

    def test_reporter_minimal(self):
        p = AGENT_PERMISSIONS[AgentRole.REPORTER]
        assert p.read_evidence
        assert not p.read_repo
        assert not p.write_repo
