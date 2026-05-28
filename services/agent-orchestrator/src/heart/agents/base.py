"""BaseAgent: abstract base for all Heart Mode agent roles."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..models import AgentRole, TaskRun


@dataclass
class AgentResult:
    """Standardized return value for agent execution."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int | None = None


class BaseAgent(ABC):
    """Abstract agent with role and permission metadata."""

    role: AgentRole

    def __init__(self) -> None:
        if not hasattr(self, "role") or self.role is None:
            raise TypeError(f"{type(self).__name__} must define a class-level `role`.")

    @abstractmethod
    def run(self, task: TaskRun) -> AgentResult:
        """Execute this agent's core logic on the given task."""
        ...

    def can_write_repo(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"{type(self).__name__}(role={self.role.value})"
