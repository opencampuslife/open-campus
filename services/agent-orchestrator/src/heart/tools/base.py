"""Heart Mode tools — base types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── Exceptions ────────────────────────────────────────────────────────────

class ToolError(Exception):
    """Base tool error."""
    pass


class ToolNotAllowed(ToolError):
    def __init__(self, tool_name: str) -> None:
        super().__init__(f"Tool not allowed: {tool_name}")
        self.tool_name = tool_name


class ToolExecutionError(ToolError):
    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(f"Tool {tool_name} failed: {reason}")
        self.tool_name = tool_name
        self.reason = reason


# ── ToolCall & ToolResult ──────────────────────────────────────────────────

@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    id: str
    tool_name: str
    input: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = True          # P3-A: always True
    status: str = "pending"        # "pending" | "done" | "failed" | "skipped"
    output: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "input": self.input,
            "dry_run": self.dry_run,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ToolResult:
    """Result returned by a tool after execution."""
    tool_call_id: str
    status: str                       # "success" | "failure" | "skipped"
    output: dict[str, Any] = field(default_factory=dict)
    side_effects: list[str] = field(default_factory=list)   # P3-A: always []
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "tool_call_id": self.tool_call_id,
            "status": self.status,
            "output": self.output,
            "side_effects": self.side_effects,
            "error": self.error,
        }


# ── BaseTool ──────────────────────────────────────────────────────────────

class BaseTool(ABC):
    """Abstract base for all Heart Mode tools."""

    name: str          # e.g. "read_files", "write_plan"
    dry_run: bool = True  # P3-A: all tools are dry-run

    @abstractmethod
    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Run the tool and return a result.

        Subclasses MUST ensure side_effects is an empty list.
        """
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"