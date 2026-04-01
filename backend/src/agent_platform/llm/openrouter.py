"""OpenRouter LLM provider implementation."""

import time
from typing import Any

import httpx

from agent_platform.llm.models import (
    LLMConfig,
    LLMResponse,
    Message,
    MessageRole,
    ToolCall,
)
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    """LLM provider backed by the OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        http_client: httpx.AsyncClient | None = None,
        event_bus: InProcessEventBus | None = None,
        agent_id: str = "system",
    ) -> None:
        self._api_key = api_key
        self._client = http_client or httpx.AsyncClient()
        self._event_bus = event_bus
        self._agent_id = agent_id

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        config: LLMConfig | None = None,
    ) -> LLMResponse:
        config = config or LLMConfig()

        # Build request
        request_body = self._build_request(messages, tools, config)

        # Emit LLM_REQUEST event
        if self._event_bus:
            await self._event_bus.emit(
                Event(
                    agent_id=self._agent_id,
                    event_type=EventType.LLM_REQUEST,
                    module="llm.openrouter",
                    payload={
                        "model": config.model,
                        "message_count": len(messages),
                    },
                )
            )

        start = time.monotonic()
        resp = await self._client.post(
            OPENROUTER_API_URL,
            json=request_body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        resp.raise_for_status()
        data = resp.json()

        # Parse response
        result = self._parse_response(data)

        # Emit LLM_RESPONSE event
        if self._event_bus:
            await self._event_bus.emit(
                Event(
                    agent_id=self._agent_id,
                    event_type=EventType.LLM_RESPONSE,
                    module="llm.openrouter",
                    payload={
                        "model": config.model,
                        "usage": result.usage,
                        "has_tool_calls": len(result.tool_calls) > 0,
                    },
                    duration_ms=duration_ms,
                )
            )

        return result

    @staticmethod
    def _build_request(
        messages: list[Message],
        tools: list[dict] | None,
        config: LLMConfig,
    ) -> dict[str, Any]:
        """Build the OpenRouter API request body."""
        body: dict[str, Any] = {
            "model": config.model,
            "messages": [_message_to_openrouter(m) for m in messages],
            "temperature": config.temperature,
        }
        if config.max_tokens is not None:
            body["max_tokens"] = config.max_tokens
        if tools:
            body["tools"] = tools
        return body

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> LLMResponse:
        """Parse OpenRouter API response into LLMResponse."""
        choice = data["choices"][0]
        message = choice["message"]

        content = message.get("content")
        tool_calls: list[ToolCall] = []

        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                args = tc.get("function", {}).get("arguments", "{}")
                if isinstance(args, str):
                    import json

                    args = json.loads(args)
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        name=tc.get("function", {}).get("name", ""),
                        arguments=args,
                    )
                )

        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            raw_response=data,
        )


def _message_to_openrouter(msg: Message) -> dict[str, Any]:
    """Convert internal Message to OpenRouter message format."""
    role_map = {
        MessageRole.HUMAN: "user",
        MessageRole.ASSISTANT: "assistant",
        MessageRole.SYSTEM: "system",
        MessageRole.TOOL_RESULT: "tool",
    }
    result: dict[str, Any] = {
        "role": role_map.get(msg.role, msg.role),
        "content": msg.content,
    }
    if msg.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return result
