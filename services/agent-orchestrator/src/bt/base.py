from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class BTStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"
    ERROR = "ERROR"


class Node(ABC):
    name: str = "Node"

    @abstractmethod
    def tick(self, ctx: "AgentContext") -> BTStatus: ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"


class ActionNode(Node):
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__


class ConditionNode(Node):
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__


class Sequence(Node):
    def __init__(self, name: str = "", children: list[Node] | None = None):
        self.name = name or "Sequence"
        self.children = children or []

    def tick(self, ctx: AgentContext) -> BTStatus:
        for child in self.children:
            status = _trace_tick(child, ctx)
            if status != BTStatus.SUCCESS:
                return status
        return BTStatus.SUCCESS


class Selector(Node):
    def __init__(self, name: str = "", children: list[Node] | None = None):
        self.name = name or "Selector"
        self.children = children or []

    def tick(self, ctx: AgentContext) -> BTStatus:
        for child in self.children:
            status = _trace_tick(child, ctx)
            if status != BTStatus.FAILURE:
                return status
        return BTStatus.FAILURE


class Inverter(Node):
    def __init__(self, name: str = "", child: Node | None = None):
        self.name = name or "Inverter"
        self.child = child

    def tick(self, ctx: AgentContext) -> BTStatus:
        if self.child is None:
            return BTStatus.ERROR
        status = _trace_tick(self.child, ctx)
        if status == BTStatus.SUCCESS:
            return BTStatus.FAILURE
        if status == BTStatus.FAILURE:
            return BTStatus.SUCCESS
        return status


class Decorator(Node):
    def __init__(self, name: str = "", child: Node | None = None):
        self.name = name or "Decorator"
        self.child = child

    def tick(self, ctx: AgentContext) -> BTStatus:
        if self.child is None:
            return BTStatus.ERROR
        return _trace_tick(self.child, ctx)


@dataclass
class AgentContext:
    user_id: str = ""
    role: str = "visitor"
    campus: str = "all"
    auth_level: str = "anonymous"
    entrypoint: str = "public_chat"

    message: str = ""
    session_id: str = ""

    normalized_message: str = ""
    intent: str = ""
    intent_detail: dict[str, Any] = field(default_factory=dict)

    permission_scope: dict[str, Any] = field(default_factory=dict)
    allowed_chunks: list[dict[str, Any]] = field(default_factory=list)
    denied_chunks: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)

    answer_draft: str = ""
    answer_final: str = ""
    compliance_passed: bool = True
    compliance_violations: list[str] = field(default_factory=list)

    active_mode: str = "admissions_consultation"
    emotion_theme: str = ""
    emotion_signal: str = ""
    crisis_risk: str = "none"
    support_strategy: str = ""
    safe_for_bridge: bool = False

    profile: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    handoff_triggered: bool = False

    profile_completeness: float = 0.0
    profile_missing_fields: list[str] = field(default_factory=list)
    profile_merge_decisions: list[dict[str, Any]] = field(default_factory=list)
    profile_needs_confirmation: list[dict[str, Any]] = field(default_factory=list)
    consultation_stage: str = ""
    recommendation_result: dict[str, Any] | None = None

    fsm_state: str = "CONSULTING"

    audit_events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    project_root: Path = field(default_factory=Path)


@dataclass
class BTResult:
    status: BTStatus
    response: dict[str, Any] = field(default_factory=dict)
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {BTStatus.SUCCESS, BTStatus.RUNNING}


def _trace_tick(node: Node, ctx: AgentContext) -> BTStatus:
    t0 = time.monotonic()
    try:
        status = node.tick(ctx)
    except Exception as exc:
        status = BTStatus.ERROR
        ctx.errors.append(f"{node.name}: {exc}")
    elapsed = int((time.monotonic() - t0) * 1000)
    ctx.audit_events.append({
        "node": node.name,
        "status": status.value,
        "duration_ms": elapsed,
    })
    return status


def run_tree(root: Node, ctx: AgentContext) -> BTResult:
    status = _trace_tick(root, ctx)
    return BTResult(
        status=status,
        response={
            "answer": ctx.answer_final,
            "intent": {"intent": ctx.intent},
            "retrieval": {
                "allowed_chunks": ctx.allowed_chunks,
                "denied_pre_filter": ctx.denied_chunks,
                "citations": ctx.citations,
                "confidence": _calc_confidence(ctx.allowed_chunks),
            },
            "compliance": {
                "passed": ctx.compliance_passed,
                "violations": ctx.compliance_violations,
            },
            "profile": ctx.profile,
            "profile_completeness": ctx.profile_completeness,
            "profile_missing_fields": ctx.profile_missing_fields,
            "profile_merge_decisions": ctx.profile_merge_decisions,
            "profile_needs_confirmation": ctx.profile_needs_confirmation,
            "consultation_stage": ctx.consultation_stage,
            "recommendation_result": ctx.recommendation_result,
            "risk_level": ctx.risk_level,
            "active_mode": ctx.active_mode,
            "handoff_triggered": ctx.handoff_triggered,
            "emotion_theme": ctx.emotion_theme,
            "crisis_risk": ctx.crisis_risk,
        },
        audit_events=list(ctx.audit_events),
        trace=list(ctx.audit_events),
    )


def _calc_confidence(chunks: list[dict[str, Any]]) -> float:
    return min(1.0, len(chunks) / 6.0)
