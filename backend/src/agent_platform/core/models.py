"""Core data models — Agent, Conversation, HITL."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from agent_platform.llm.models import Message


class AgentStatus(StrEnum):
    """Agent lifecycle status."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"


class HITLPolicy(StrEnum):
    """Human-in-the-loop approval policy."""

    ALWAYS_ASK = "always_ask"
    DANGEROUS_ONLY = "dangerous_only"
    NEVER = "never"


class AgentConfig(BaseModel):
    """Configuration for an agent instance."""

    model: str = "openai/gpt-4.1-mini"
    temperature: float = 0.7
    max_iterations: int = 10
    system_prompt: str = "You are a helpful assistant."
    allowed_tools: list[str] = Field(default_factory=list)
    hitl_policy: HITLPolicy = HITLPolicy.NEVER


class Agent(BaseModel):
    """An agent instance."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    status: AgentStatus = AgentStatus.IDLE
    config: AgentConfig = Field(default_factory=AgentConfig)
    parent_agent_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Conversation(BaseModel):
    """A conversation between a human and an agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    messages: list[Message] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Response from an agent run."""

    agent_id: str
    content: str | None = None
    conversation_id: str | None = None
    events_emitted: int = 0
