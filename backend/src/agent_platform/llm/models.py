"""LLM data models — messages, tool calls, responses, config."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    """Role of a message in a conversation."""

    HUMAN = "human"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_RESULT = "tool_result"


class ToolCall(BaseModel):
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """A single message in a conversation."""

    role: MessageRole
    content: str | list[dict[str, Any]] = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    timestamp: str | None = None


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    raw_response: dict[str, Any] | None = None


class LLMConfig(BaseModel):
    """Configuration for an LLM call."""

    model: str = "minimax/minimax-m2.7"
    temperature: float = 0.7
    max_tokens: int | None = None
