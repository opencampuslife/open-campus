"""PlannerAgent — generates a minimal TaskGraph from a goal string.

P2-A: rule-based decomposition. No LLM. Deterministic templates based on
keyword matching. Later phases will replace with LLM-driven planning.
"""

from __future__ import annotations

import re
from typing import ClassVar

from ..models import AgentRole, RiskLevel, TaskGraph, TaskNode, TaskRun
from .base import AgentResult, BaseAgent


# ── Task kind detection ───────────────────────────────────────────────────

_FEATURE_PATTERNS = re.compile(
    r"\b(add|implement|build|create|develop|introduce|support|enable)\b",
    re.IGNORECASE,
)
_FIX_PATTERNS = re.compile(
    r"\b(fix|repair|resolve|patch|bug|hotfix|correct)\b",
    re.IGNORECASE,
)
_DOCS_PATTERNS = re.compile(
    r"\b(doc|document|write|spec|design|plan|proposal|contract)\b",
    re.IGNORECASE,
)
_REFACTOR_PATTERNS = re.compile(
    r"\b(refactor|restructure|migrate|upgrade|clean|simplify|reorganize)\b",
    re.IGNORECASE,
)


def _classify_goal(goal: str) -> str:
    """Classify goal into a task kind: feature, fix, docs, refactor, generic."""
    if _FEATURE_PATTERNS.search(goal):
        return "feature"
    if _FIX_PATTERNS.search(goal):
        return "fix"
    if _DOCS_PATTERNS.search(goal):
        return "docs"
    if _REFACTOR_PATTERNS.search(goal):
        return "refactor"
    return "generic"


# ── Template DAGs ─────────────────────────────────────────────────────────

def _make_node(
    node_id: str,
    phase: int,
    desc: str,
    owner: AgentRole,
    depends: list[str] | None = None,
    criteria: list[str] | None = None,
) -> TaskNode:
    return TaskNode(
        id=node_id,
        phase=phase,
        description=desc,
        owner_agent=owner,
        depends_on=depends or [],
        acceptance_criteria=criteria or [],
    )


def _feature_dag() -> TaskGraph:
    nodes = [
        _make_node("tn_01", 1, "Analyze requirements and scope", AgentRole.PLANNER,
                   criteria=["Scope is clearly defined", "Dependencies identified"]),
        _make_node("tn_02", 1, "Research codebase and relevant docs", AgentRole.RESEARCHER,
                   depends=["tn_01"],
                   criteria=["Key files and patterns identified"]),
        _make_node("tn_03", 2, "Produce implementation plan", AgentRole.ENGINEER,
                   depends=["tn_01", "tn_02"],
                   criteria=["Plan covers all acceptance criteria"]),
        _make_node("tn_04", 2, "Review implementation plan", AgentRole.REVIEWER,
                   depends=["tn_03"],
                   criteria=["No architectural or security concerns"]),
        _make_node("tn_05", 3, "Generate delivery report", AgentRole.REPORTER,
                   depends=["tn_04"],
                   criteria=["Report includes task summary and next steps"]),
    ]
    edges = [
        {"from": "tn_01", "to": "tn_02", "type": "depends_on"},
        {"from": "tn_01", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_02", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_03", "to": "tn_04", "type": "depends_on"},
        {"from": "tn_04", "to": "tn_05", "type": "depends_on"},
    ]
    return TaskGraph(nodes=nodes, edges=edges)


def _fix_dag() -> TaskGraph:
    nodes = [
        _make_node("tn_01", 1, "Reproduce and isolate the issue", AgentRole.RESEARCHER,
                   criteria=["Root cause identified or narrowed down"]),
        _make_node("tn_02", 1, "Propose fix approach", AgentRole.PLANNER,
                   depends=["tn_01"],
                   criteria=["Fix approach is safe and minimal"]),
        _make_node("tn_03", 2, "Generate patch plan", AgentRole.ENGINEER,
                   depends=["tn_01", "tn_02"],
                   criteria=["Patch covers root cause, not just symptoms"]),
        _make_node("tn_04", 2, "Review patch for regressions", AgentRole.REVIEWER,
                   depends=["tn_03"],
                   criteria=["No regression risk identified"]),
        _make_node("tn_05", 3, "Generate fix report", AgentRole.REPORTER,
                   depends=["tn_04"],
                   criteria=["Report includes root cause analysis"]),
    ]
    edges = [
        {"from": "tn_01", "to": "tn_02", "type": "depends_on"},
        {"from": "tn_01", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_02", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_03", "to": "tn_04", "type": "depends_on"},
        {"from": "tn_04", "to": "tn_05", "type": "depends_on"},
    ]
    return TaskGraph(nodes=nodes, edges=edges)


def _docs_dag() -> TaskGraph:
    nodes = [
        _make_node("tn_01", 1, "Research existing docs and context", AgentRole.RESEARCHER,
                   criteria=["Gathered all relevant reference material"]),
        _make_node("tn_02", 1, "Draft document outline", AgentRole.PLANNER,
                   depends=["tn_01"],
                   criteria=["Outline covers all required sections"]),
        _make_node("tn_03", 2, "Write document content", AgentRole.ENGINEER,
                   depends=["tn_02"],
                   criteria=["Content is complete and accurate"]),
        _make_node("tn_04", 2, "Review document", AgentRole.REVIEWER,
                   depends=["tn_03"],
                   criteria=["No factual errors or gaps"]),
        _make_node("tn_05", 3, "Finalize and deliver", AgentRole.REPORTER,
                   depends=["tn_04"],
                   criteria=["Document is ready for publication"]),
    ]
    edges = [
        {"from": "tn_01", "to": "tn_02", "type": "depends_on"},
        {"from": "tn_02", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_03", "to": "tn_04", "type": "depends_on"},
        {"from": "tn_04", "to": "tn_05", "type": "depends_on"},
    ]
    return TaskGraph(nodes=nodes, edges=edges)


def _refactor_dag() -> TaskGraph:
    nodes = [
        _make_node("tn_01", 1, "Analyze current code structure", AgentRole.RESEARCHER,
                   criteria=["All affected modules and dependencies mapped"]),
        _make_node("tn_02", 1, "Design target architecture", AgentRole.PLANNER,
                   depends=["tn_01"],
                   criteria=["Target architecture preserves existing behavior"]),
        _make_node("tn_03", 2, "Produce refactoring plan", AgentRole.ENGINEER,
                   depends=["tn_01", "tn_02"],
                   criteria=["Plan is incremental and reversible"]),
        _make_node("tn_04", 2, "Safety review", AgentRole.REVIEWER,
                   depends=["tn_03"],
                   criteria=["No breaking changes without migration path"]),
        _make_node("tn_05", 3, "Generate refactoring report", AgentRole.REPORTER,
                   depends=["tn_04"],
                   criteria=["Report includes migration guide"]),
    ]
    edges = [
        {"from": "tn_01", "to": "tn_02", "type": "depends_on"},
        {"from": "tn_01", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_02", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_03", "to": "tn_04", "type": "depends_on"},
        {"from": "tn_04", "to": "tn_05", "type": "depends_on"},
    ]
    return TaskGraph(nodes=nodes, edges=edges)


def _generic_dag() -> TaskGraph:
    nodes = [
        _make_node("tn_01", 1, "Clarify and scope the goal", AgentRole.PLANNER,
                   criteria=["Goal is unambiguous and bounded"]),
        _make_node("tn_02", 1, "Gather context", AgentRole.RESEARCHER,
                   depends=["tn_01"],
                   criteria=["Enough context to proceed"]),
        _make_node("tn_03", 2, "Produce actionable plan", AgentRole.ENGINEER,
                   depends=["tn_01", "tn_02"],
                   criteria=["Plan has clear deliverables"]),
        _make_node("tn_04", 2, "Review plan", AgentRole.REVIEWER,
                   depends=["tn_03"],
                   criteria=["Plan is feasible and safe"]),
        _make_node("tn_05", 3, "Generate summary report", AgentRole.REPORTER,
                   depends=["tn_04"],
                   criteria=["Report is self-contained"]),
    ]
    edges = [
        {"from": "tn_01", "to": "tn_02", "type": "depends_on"},
        {"from": "tn_01", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_02", "to": "tn_03", "type": "depends_on"},
        {"from": "tn_03", "to": "tn_04", "type": "depends_on"},
        {"from": "tn_04", "to": "tn_05", "type": "depends_on"},
    ]
    return TaskGraph(nodes=nodes, edges=edges)


_KIND_MAP: dict[str, type] = {
    "feature": _feature_dag,
    "fix": _fix_dag,
    "docs": _docs_dag,
    "refactor": _refactor_dag,
    "generic": _generic_dag,
}

# ── PlannerAgent ──────────────────────────────────────────────────────────


class PlannerAgent(BaseAgent):
    """Generates a task DAG from a natural-language goal.

    P2-A: rule-based keyword matching → deterministic template.
    No LLM. Designed to be replaced by LLM-driven planning in later phases.
    """

    role: ClassVar[AgentRole] = AgentRole.PLANNER

    def run(self, task: TaskRun) -> AgentResult:
        kind = _classify_goal(task.goal)
        factory = _KIND_MAP.get(kind, _generic_dag)
        try:
            graph = factory()
        except Exception as exc:
            return AgentResult(success=False, error=str(exc))

        return AgentResult(
            success=True,
            data={"task_kind": kind, "node_count": graph.node_count},
        )

    @staticmethod
    def generate_graph(goal: str) -> tuple[TaskGraph, str]:
        """Return (TaskGraph, task_kind) for a given goal string."""
        kind = _classify_goal(goal)
        factory = _KIND_MAP.get(kind, _generic_dag)
        return factory(), kind
