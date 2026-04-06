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


class AgentRetryConfig(BaseModel):
    """Per-agent retry override. None fields fall back to platform defaults."""

    max_retries: int | None = None
    base_delay: float | None = None
    max_delay: float | None = None
    timeout: float | None = None


class AgentConfig(BaseModel):
    """Configuration for an agent instance."""

    model: str = "openai/gpt-4.1-mini"
    temperature: float = 0.7
    max_iterations: int = 10
    system_prompt: str = "You are a helpful assistant."
    allowed_tools: list[str] = Field(default_factory=list)
    hitl_policy: HITLPolicy = HITLPolicy.NEVER
    hitl_timeout_seconds: float = 300
    retry: AgentRetryConfig = Field(default_factory=AgentRetryConfig)
    prune_threshold: float = 0.1
    prune_max_entries: int = 500
    max_context_tokens: int = 100_000
    memory_top_k: int = 5
    summary_model: str | None = None
    extraction_model: str | None = None
    orchestration_model: str | None = None
    max_subtasks: int = 10
    auto_extract: bool = True
    memory_sharing: dict[str, str] | None = None
    allowed_mcp_servers: list[str] | None = None


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


class MessageType(StrEnum):
    """Type of inter-agent message."""

    TASK = "task"
    RESULT = "result"
    QUESTION = "question"
    ANSWER = "answer"
    GUIDANCE = "guidance"
    STATUS_UPDATE = "status_update"
    WAKE = "wake"


class AgentMessage(BaseModel):
    """A message between agents or from human to agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    from_agent_id: str
    to_agent_id: str
    content: str
    message_type: MessageType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    in_reply_to: str | None = None
