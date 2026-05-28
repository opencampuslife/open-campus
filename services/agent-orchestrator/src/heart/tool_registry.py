"""ToolRegistry — maps tool names to BaseTool instances.

P3-A: only dry-run tools are registered. No write-capable tools.
Dynamic registration of unknown tools is forbidden.
"""

from __future__ import annotations

from typing import Any

from .tools.base import BaseTool, ToolNotAllowed
from .tools.dry_run import DRY_RUN_TOOLS


class ToolRegistry:
    """Central registry for Heart Mode tools.

    P3-A behaviour:
        - Pre-registers only DRY_RUN_TOOLS on init.
        - get() raises ToolNotAllowed for any unknown tool name.
        - No dynamic registration allowed.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        for tool_cls in DRY_RUN_TOOLS:
            tool = tool_cls()
            self._tools[tool.name] = tool

    def get(self, tool_name: str) -> BaseTool:
        """Return a tool by name, or raise ToolNotAllowed."""
        if tool_name not in self._tools:
            raise ToolNotAllowed(tool_name)
        return self._tools[tool_name]

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return sorted(self._tools.keys())

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self._tools