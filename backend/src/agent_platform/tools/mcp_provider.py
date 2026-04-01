"""MCP tool provider — stub implementation with configurable tools."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from agent_platform.tools.models import Tool, ToolResult


class MCPToolProvider:
    """Stub MCP provider with pre-configured tools and handlers.

    This implements the ToolProvider interface with injectable handlers,
    making it easy to test. A real MCP transport (stdio/SSE) can be
    swapped in later.
    """

    def __init__(self, server_name: str = "mcp-server") -> None:
        self._server_name = server_name
        self._tools: dict[str, Tool] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[str]]] = {}

    def register_tool(
        self,
        tool: Tool,
        handler: Callable[[dict[str, Any]], Awaitable[str]],
    ) -> None:
        """Register a tool with its handler."""
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    async def list_tools(self) -> list[Tool]:
        """Return registered tools."""
        return list(self._tools.values())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Call a tool by name."""
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}",
            )

        start = time.monotonic()
        try:
            output = await handler(arguments)
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
