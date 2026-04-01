"""ToolProvider protocol."""

from typing import Any, Protocol, runtime_checkable

from agent_platform.tools.models import Tool, ToolResult


@runtime_checkable
class ToolProvider(Protocol):
    """Abstract interface for tool providers."""

    async def list_tools(self) -> list[Tool]: ...

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolResult: ...
