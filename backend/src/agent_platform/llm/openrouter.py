"""OpenRouter LLM provider implementation."""

import json
import logging
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
from agent_platform.observation.cost_tracker import _get_cost_per_million
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    """LLM provider backed by the OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        http_client: httpx.AsyncClient | None = None,
        event_bus: InProcessEventBus | None = None,
        agent_id: str = "system",
        timeout: float = 60.0,
        default_model: str = "openai/gpt-4.1-mini",
    ) -> None:
        self._api_key = api_key
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0)
        )
        self._event_bus = event_bus
        self._agent_id = agent_id
        self._default_model = default_model
        self._current_agent_id: str | None = None
        self._current_retry: dict | None = None  # per-agent override

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        config: LLMConfig | None = None,
    ) -> LLMResponse:
        config = config or LLMConfig()
        if config.model is None:
            config.model = self._default_model
        agent_id = self._current_agent_id or self._agent_id

        # Build request
        request_body = self._build_request(messages, tools, config)

        # Emit LLM_REQUEST event
        if self._event_bus:
            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.LLM_REQUEST,
                    module="llm.openrouter",
                    payload={
                        "model": config.model,
                        "message_count": len(messages),
                        "has_tools": bool(tools),
                    },
                )
            )

        # Log the request for debugging
        logger.debug(
            "OpenRouter request: %s",
            json.dumps(request_body, default=str)[:2000],
        )

        from agent_platform.llm.retry import async_retry

        retry_kw = self._current_retry or {}

        start = time.monotonic()
        resp = await async_retry(
            lambda: self._client.post(
                OPENROUTER_API_URL,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            ),
            **retry_kw,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        data = resp.json()

        # Handle HTTP errors with response body context
        if resp.status_code >= 400:
            err = data.get("error", {})
            if isinstance(err, dict):
                msg = err.get("message", "")
                metadata = err.get("metadata", {})
                raw = metadata.get("raw", "") if metadata else ""
                detail = f"{msg}. {raw}".strip(". ") if raw else msg
            else:
                detail = str(err)
            logger.error(
                "OpenRouter %d for model %s: %s | body: %s",
                resp.status_code,
                config.model,
                detail,
                json.dumps(data)[:500],
            )
            raise RuntimeError(f"OpenRouter API error ({resp.status_code}): {detail}")

        # OpenRouter may return errors with 200 status
        if "error" in data:
            err = data["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise RuntimeError(f"OpenRouter API error: {msg}")

        if "choices" not in data or not data["choices"]:
            raise RuntimeError(f"OpenRouter returned unexpected response: {data}")

        # Parse response
        result = self._parse_response(data)

        # Compute cost
        _usage = result.usage or {}
        _prompt_tok = _usage.get("prompt_tokens", 0) or 0
        _compl_tok = _usage.get("completion_tokens", 0) or 0
        _in_rate, _out_rate = _get_cost_per_million(config.model)
        _cost = _prompt_tok / 1_000_000 * _in_rate + _compl_tok / 1_000_000 * _out_rate

        # Emit LLM_RESPONSE event
        if self._event_bus:
            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.LLM_RESPONSE,
                    module="llm.openrouter",
                    payload={
                        "model": config.model,
                        "usage": result.usage,
                        "has_tool_calls": len(result.tool_calls) > 0,
                        "content_preview": (
                            result.content[:200] if result.content else None
                        ),
                        "tool_calls": [
                            {"name": tc.name, "arguments": tc.arguments}
                            for tc in result.tool_calls
                        ],
                        "cost_usd": round(_cost, 6),
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
        # Repair old conversations: match tool_call_ids from assistant messages
        _repair_tool_call_ids(messages)

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
    # Tool result messages must include tool_call_id
    if msg.role == MessageRole.TOOL_RESULT and msg.tool_call_id:
        result["tool_call_id"] = msg.tool_call_id
    if msg.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": (
                        json.dumps(tc.arguments)
                        if isinstance(tc.arguments, dict)
                        else tc.arguments
                    ),
                },
            }
            for tc in msg.tool_calls
        ]
    return result


def _repair_tool_call_ids(messages: list[Message]) -> None:
    """Fix tool result messages missing tool_call_id.

    Matches them to tool_calls from the preceding assistant message.
    This handles conversations persisted before tool_call_id was added.
    """
    pending_tool_call_ids: list[str] = []
    for msg in messages:
        if msg.role == MessageRole.ASSISTANT and msg.tool_calls:
            pending_tool_call_ids = [tc.id for tc in msg.tool_calls]
        elif msg.role == MessageRole.TOOL_RESULT and not msg.tool_call_id:
            if pending_tool_call_ids:
                msg.tool_call_id = pending_tool_call_ids.pop(0)
            else:
                msg.tool_call_id = "call_unknown"
