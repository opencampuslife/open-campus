"""Dry-run tool implementations for P3-A.

All tools return ToolResult with side_effects=[].
No real GitHub write. No CI run. No LLM.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from .base import BaseTool, ToolCall, ToolResult


def _call_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


# ── NoOpTool ───────────────────────────────────────────────────────────────

class NoOpTool(BaseTool):
    """No-operation tool: returns a dry-run success with no side effects."""

    name: ClassVar[str] = "noop"

    def execute(self, tool_call: ToolCall) -> ToolResult:
        return ToolResult(
            tool_call_id=tool_call.id,
            status="success",
            output={"action": "noop", "dry_run": True},
            side_effects=[],
        )


# ── ReadFilesTool ────────────────────────────────────────────────────────

class ReadFilesTool(BaseTool):
    """Dry-run file reading. Simulates reading files without accessing the filesystem."""

    name: ClassVar[str] = "read_files"

    def execute(self, tool_call: ToolCall) -> ToolResult:
        paths = tool_call.input.get("paths", [])
        return ToolResult(
            tool_call_id=tool_call.id,
            status="success",
            output={
                "action": "read_files",
                "dry_run": True,
                "would_read": [str(p) for p in paths],
                "note": "P3-A dry-run: no real filesystem access",
            },
            side_effects=[],
        )


# ── WritePlanTool ────────────────────────────────────────────────────────

class WritePlanTool(BaseTool):
    """Dry-run plan writing. Simulates producing a written plan without file writes."""

    name: ClassVar[str] = "write_plan"

    def execute(self, tool_call: ToolCall) -> ToolResult:
        content = tool_call.input.get("content", "")
        path = tool_call.input.get("path", "")
        return ToolResult(
            tool_call_id=tool_call.id,
            status="success",
            output={
                "action": "write_plan",
                "dry_run": True,
                "would_write": {
                    "path": str(path),
                    "content_preview": str(content)[:200] if content else "",
                },
                "note": "P3-A dry-run: no real file write",
            },
            side_effects=[],
        )


# ── ReviewPlanTool ───────────────────────────────────────────────────────

class ReviewPlanTool(BaseTool):
    """Dry-run plan review. Simulates code review without accessing the repository."""

    name: ClassVar[str] = "review_plan"

    def execute(self, tool_call: ToolCall) -> ToolResult:
        scope = tool_call.input.get("scope", "")
        return ToolResult(
            tool_call_id=tool_call.id,
            status="success",
            output={
                "action": "review_plan",
                "dry_run": True,
                "would_review": str(scope),
                "note": "P3-A dry-run: no real code review",
            },
            side_effects=[],
        )


# ── GenerateReportTool ───────────────────────────────────────────────────

class GenerateReportTool(BaseTool):
    """Dry-run report generation. Simulates report output without file writes."""

    name: ClassVar[str] = "generate_report"

    def execute(self, tool_call: ToolCall) -> ToolResult:
        task_id = tool_call.input.get("task_id", "")
        return ToolResult(
            tool_call_id=tool_call.id,
            status="success",
            output={
                "action": "generate_report",
                "dry_run": True,
                "would_include": ["task_summary", "evidence_chain", "next_steps"],
                "note": "P3-A dry-run: no real file write",
            },
            side_effects=[],
        )


# ── Dry-run tool registry ─────────────────────────────────────────────────

DRY_RUN_TOOLS: list[type[BaseTool]] = [
    NoOpTool,
    ReadFilesTool,
    WritePlanTool,
    ReviewPlanTool,
    GenerateReportTool,
]