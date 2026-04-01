"""Prompt macro model and provider."""

import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agent_platform.llm.models import LLMResponse, Message, MessageRole
from agent_platform.tools.models import Tool, ToolResult, ToolType


class PromptMacro(BaseModel):
    """A parameterized prompt template that executes as an LLM sub-call."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    template: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_instructions: str = ""


class PromptMacroProvider:
    """ToolProvider that executes prompt macros via LLM sub-calls."""

    def __init__(self, llm_provider: Any) -> None:
        self._llm = llm_provider
        self._macros: dict[str, PromptMacro] = {}

    def add_macro(self, macro: PromptMacro) -> None:
        """Register a prompt macro."""
        self._macros[macro.name] = macro

    def remove_macro(self, name: str) -> None:
        """Remove a prompt macro."""
        self._macros.pop(name, None)

    async def list_tools(self) -> list[Tool]:
        """Return macros as tools."""
        return [
            Tool(
                name=macro.name,
                description=macro.description,
                input_schema=macro.parameters,
                tool_type=ToolType.PROMPT_MACRO,
                source=macro.id,
            )
            for macro in self._macros.values()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Expand template and execute as LLM sub-call."""
        macro = self._macros.get(name)
        if macro is None:
            return ToolResult(
                success=False,
                error=f"Unknown macro: {name}",
            )

        # Expand template
        expanded = macro.template
        for key, value in arguments.items():
            expanded = expanded.replace(f"{{{{{key}}}}}", str(value))

        # Build messages for LLM sub-call
        messages = [
            Message(role=MessageRole.HUMAN, content=expanded),
        ]
        if macro.output_instructions:
            messages.insert(
                0,
                Message(
                    role=MessageRole.SYSTEM,
                    content=macro.output_instructions,
                ),
            )

        start = time.monotonic()
        try:
            response: LLMResponse = await self._llm.complete(messages)
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=True,
                output=response.content or "",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
