"""Unit tests for ToolRegistry and dry-run tools."""

from __future__ import annotations

import pytest

from heart.tools.base import ToolNotAllowed, BaseTool, ToolCall, ToolResult
from heart.tools.dry_run import (
    NoOpTool, ReadFilesTool, WritePlanTool,
    ReviewPlanTool, GenerateReportTool, DRY_RUN_TOOLS,
)
from heart.tool_registry import ToolRegistry


# ── Dry-run tools ──────────────────────────────────────────────────────────

class TestDryRunTools:
    def _run(self, tool: BaseTool, input_data: dict) -> ToolResult:
        call = ToolCall(id="call_test", tool_name=tool.name, input=input_data, dry_run=True)
        return tool.execute(call)

    def test_noop_side_effects_empty(self):
        result = self._run(NoOpTool(), {})
        assert result.side_effects == []
        assert result.status == "success"

    def test_read_files_side_effects_empty(self):
        result = self._run(ReadFilesTool(), {"paths": ["/a/b.py", "/c/d.py"]})
        assert result.side_effects == []
        assert result.status == "success"
        assert "would_read" in result.output

    def test_write_plan_side_effects_empty(self):
        result = self._run(WritePlanTool(), {"path": "/x/y.py", "content": "hello world"})
        assert result.side_effects == []
        assert result.status == "success"
        assert result.output["dry_run"] is True

    def test_review_plan_side_effects_empty(self):
        result = self._run(ReviewPlanTool(), {"scope": "services/agent-orchestrator"})
        assert result.side_effects == []
        assert result.status == "success"

    def test_generate_report_side_effects_empty(self):
        result = self._run(GenerateReportTool(), {"task_id": "task_001"})
        assert result.side_effects == []
        assert result.status == "success"

    def test_all_tools_are_dry_run(self):
        for tool_cls in DRY_RUN_TOOLS:
            tool = tool_cls()
            assert tool.dry_run is True


# ── ToolRegistry ──────────────────────────────────────────────────────────

class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    def test_known_tools_available(self, registry):
        for name in ["noop", "read_files", "write_plan", "review_plan", "generate_report"]:
            tool = registry.get(name)
            assert tool.name == name

    def test_unknown_tool_raises(self, registry):
        for bad in ["github_write", "shell", "deploy", "exec", "delete_branch"]:
            with pytest.raises(ToolNotAllowed) as exc_info:
                registry.get(bad)
            assert bad in str(exc_info.value)

    def test_list_tools(self, registry):
        tools = registry.list_tools()
        assert "noop" in tools
        assert "write_plan" in tools
        assert "generate_report" in tools
        assert "github_write" not in tools
        assert "shell" not in tools

    def test_is_allowed(self, registry):
        assert registry.is_allowed("noop") is True
        assert registry.is_allowed("read_files") is True
        assert registry.is_allowed("github_write") is False
        assert registry.is_allowed("deploy") is False

    def test_github_write_not_registered(self, registry):
        # explicit check: github_write is never in registry
        assert "github_write" not in registry.list_tools()