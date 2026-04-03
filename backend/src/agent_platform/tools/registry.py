"""ToolRegistry — aggregates tools from multiple providers."""

from typing import Any

from agent_platform.tools.models import Tool, ToolResult, ToolType
from agent_platform.tools.provider import ToolProvider


class ToolRegistry:
    """Aggregates tools from multiple providers and routes calls."""

    def __init__(self) -> None:
        self._providers: list[ToolProvider] = []
        self._tool_map: dict[str, ToolProvider] = {}

    def register_provider(self, provider: ToolProvider) -> None:
        """Register a tool provider."""
        self._providers.append(provider)

    async def list_tools(
        self,
        allowed_mcp_servers: list[str] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> list[Tool]:
        """Return combined tool list, optionally filtered."""
        tools: list[Tool] = []
        self._tool_map.clear()
        for provider in self._providers:
            provider_tools = await provider.list_tools()
            for tool in provider_tools:
                self._tool_map[tool.name] = provider
                if not _tool_passes_filters(
                    tool, allowed_mcp_servers, allowed_tools
                ):
                    continue
                tools.append(tool)
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        """Route a tool call to the correct provider."""
        if not self._tool_map:
            await self.list_tools()

        provider = self._tool_map.get(name)
        if provider is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}",
            )
        return await provider.call_tool(name, arguments)

    async def get_tools_schema(
        self,
        allowed_mcp_servers: list[str] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return tools in OpenAI function-calling format."""
        tools = await self.list_tools(
            allowed_mcp_servers=allowed_mcp_servers,
            allowed_tools=allowed_tools,
        )
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ]


def _tool_passes_filters(
    tool: Tool,
    allowed_mcp_servers: list[str] | None,
    allowed_tools: list[str] | None,
) -> bool:
    """Check if a tool passes the active filters."""
    # allowed_tools is a strict whitelist — if set, tool must be in it
    if allowed_tools is not None:
        if tool.name not in allowed_tools:
            return False

    # allowed_mcp_servers only filters MCP tools
    if allowed_mcp_servers is not None:
        if tool.tool_type == ToolType.MCP:
            if tool.source not in allowed_mcp_servers:
                return False

    return True
