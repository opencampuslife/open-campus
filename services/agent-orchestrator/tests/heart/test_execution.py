"""Unit tests for ExecutionPlan, ExecutionStep, and ExecutionPlanner."""

from __future__ import annotations

import pytest

from heart.execution import ExecutionPlanner, ExecutionPlan, ExecutionStep
from heart.models import AgentRole, TaskGraph, TaskNode, TaskRun, RiskLevel


class TestExecutionStep:
    def test_minimal(self):
        step = ExecutionStep(id="step_1", title="Analyze", tool_name="noop")
        assert step.id == "step_1"
        assert step.status == "pending"
        assert step.risk_level == "low"
        assert step.requires_approval is False

    def test_to_dict(self):
        step = ExecutionStep(id="step_2", title="Write plan", tool_name="write_plan",
                              requires_approval=True)
        d = step.to_dict()
        assert d["id"] == "step_2"
        assert d["tool_name"] == "write_plan"
        assert d["requires_approval"] is True


class TestExecutionPlan:
    def test_step_count(self):
        plan = ExecutionPlan(task_id="task_001")
        assert plan.step_count == 0
        plan.steps = [
            ExecutionStep(id="step_1", title="A", tool_name="noop"),
            ExecutionStep(id="step_2", title="B", tool_name="noop"),
        ]
        assert plan.step_count == 2

    def test_to_dict(self):
        plan = ExecutionPlan(task_id="task_001", dry_run=True)
        plan.steps = [ExecutionStep(id="step_1", title="Analyze", tool_name="noop")]
        d = plan.to_dict()
        assert d["task_id"] == "task_001"
        assert d["dry_run"] is True
        assert d["step_count"] == 1
        assert len(d["steps"]) == 1

    def test_update_status(self):
        plan = ExecutionPlan(task_id="task_001")
        plan.update_status("in_progress")
        assert plan.status == "in_progress"
        assert plan.updated_at is not None


class TestExecutionPlanner:
    @pytest.fixture
    def planner(self):
        return ExecutionPlanner()

    @pytest.fixture
    def task_with_graph(self):
        return _make_task("Add Heart Mode runtime MVP", "medium", [
            ("tn_01", 1, "Analyze requirements", AgentRole.PLANNER),
            ("tn_02", 1, "Research codebase", AgentRole.RESEARCHER),
            ("tn_03", 2, "Implement feature", AgentRole.ENGINEER),
            ("tn_04", 2, "Review implementation", AgentRole.REVIEWER),
            ("tn_05", 3, "Generate report", AgentRole.REPORTER),
        ])

    def test_plan_derives_steps_from_graph(self, planner, task_with_graph):
        plan = planner.plan(task_with_graph, task_with_graph.task_graph)
        assert plan.task_id == task_with_graph.task_id
        assert plan.dry_run is True
        assert plan.step_count >= 1
        assert plan.status == "planned"

    def test_steps_from_graph_nodes(self, planner, task_with_graph):
        plan = planner.plan(task_with_graph, task_with_graph.task_graph)
        assert plan.step_count == len(task_with_graph.task_graph.nodes)

    def test_last_step_generates_report(self, planner, task_with_graph):
        plan = planner.plan(task_with_graph, task_with_graph.task_graph)
        assert plan.steps[-1].tool_name == "generate_report"

    def test_steps_have_unique_ids(self, planner, task_with_graph):
        plan = planner.plan(task_with_graph, task_with_graph.task_graph)
        ids = [s.id for s in plan.steps]
        assert len(ids) == len(set(ids))

    def test_analyze_step_uses_read_files(self, planner):
        node = TaskNode(id="tn_01", phase=1, description="Analyze requirements",
                        owner_agent=AgentRole.PLANNER)
        step = planner._node_to_step(1, node)
        assert step.tool_name == "read_files"

    def test_produce_step_uses_write_plan(self, planner):
        node = TaskNode(id="tn_02", phase=2, description="Produce implementation plan",
                        owner_agent=AgentRole.ENGINEER)
        step = planner._node_to_step(2, node)
        assert step.tool_name == "write_plan"

    def test_review_step_uses_review_plan(self, planner):
        node = TaskNode(id="tn_03", phase=2, description="Review implementation",
                        owner_agent=AgentRole.REVIEWER)
        step = planner._node_to_step(3, node)
        assert step.tool_name == "review_plan"

    def test_deliver_step_uses_generate_report(self, planner):
        node = TaskNode(id="tn_04", phase=3, description="Finalize and deliver",
                        owner_agent=AgentRole.REPORTER)
        step = planner._node_to_step(4, node)
        assert step.tool_name == "generate_report"

    def test_unknown_keyword_defaults_to_noop(self, planner):
        node = TaskNode(id="tn_05", phase=1, description="Do something unusual",
                        owner_agent=AgentRole.PLANNER)
        step = planner._node_to_step(5, node)
        assert step.tool_name == "noop"

    def test_executor_role_step_risk_medium(self, planner):
        node = TaskNode(id="tn_01", phase=1, description="Implement feature",
                        owner_agent=AgentRole.EXECUTOR)
        step = planner._node_to_step(1, node)
        assert step.risk_level == "medium"

    def test_non_executor_role_step_risk_low(self, planner):
        node = TaskNode(id="tn_01", phase=1, description="Analyze requirements",
                        owner_agent=AgentRole.PLANNER)
        step = planner._node_to_step(1, node)
        assert step.risk_level == "low"


# ── helpers ────────────────────────────────────────────────────────────────

def _make_task(goal: str, risk: str, node_specs: list) -> TaskRun:
    risk_level = RiskLevel(risk)
    task = TaskRun(task_id="task_p3test001", goal=goal, risk_level=risk_level)

    nodes = []
    for nid, phase, desc, role in node_specs:
        nodes.append(TaskNode(id=nid, phase=phase, description=desc, owner_agent=role))

    task.task_graph = TaskGraph(nodes=nodes, edges=[])
    return task