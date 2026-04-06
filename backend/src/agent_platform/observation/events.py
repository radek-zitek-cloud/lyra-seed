"""Event models, types, and filters."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Types of events emitted by the platform."""

    LLM_REQUEST = "llm_request"
    LLM_TOKEN = "llm_token"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    AGENT_SPAWN = "agent_spawn"
    AGENT_COMPLETE = "agent_complete"
    HITL_REQUEST = "hitl_request"
    HITL_RESPONSE = "hitl_response"
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    ERROR = "error"


class Event(BaseModel):
    """A single platform event."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_id: str
    event_type: EventType
    parent_event_id: UUID | None = None
    module: str
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None


class EventFilter(BaseModel):
    """Filter criteria for querying events."""

    agent_id: str | None = None
    event_types: list[EventType] | None = None
    time_from: datetime | None = None
    time_to: datetime | None = None
    module: str | None = None
    parent_event_id: UUID | None = None
