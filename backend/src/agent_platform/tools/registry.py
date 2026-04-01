"""ToolRegistry — aggregates tools from multiple providers."""

from typing import Any

from agent_platform.tools.models import Tool, ToolResult
from agent_platform.tools.provider import ToolProvider


class ToolRegistry:
    """Aggregates tools from multiple providers and routes calls."""

    def __init__(self) -> None:
        self._providers: list[ToolProvider] = []
        self._tool_map: dict[str, ToolProvider] = {}

    def register_provider(self, provider: ToolProvider) -> None:
        """Register a tool provider."""
        self._providers.append(provider)

    async def list_tools(self) -> list[Tool]:
        """Return combined tool list from all providers."""
        tools: list[Tool] = []
        self._tool_map.clear()
        for provider in self._providers:
            provider_tools = await provider.list_tools()
            for tool in provider_tools:
                tools.append(tool)
                self._tool_map[tool.name] = provider
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Route a tool call to the correct provider."""
        # Rebuild map if empty
        if not self._tool_map:
            await self.list_tools()

        provider = self._tool_map.get(name)
        if provider is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}",
            )
        return await provider.call_tool(name, arguments)

    async def get_tools_schema(self) -> list[dict[str, Any]]:
        """Return tools in OpenAI function-calling JSON Schema format."""
        tools = await self.list_tools()
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
