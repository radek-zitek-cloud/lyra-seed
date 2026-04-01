"""LLM provider protocol."""

from typing import Protocol, runtime_checkable

from agent_platform.llm.models import LLMConfig, LLMResponse, Message, ToolCall


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract interface for LLM providers."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        config: LLMConfig | None = None,
    ) -> LLMResponse: ...
