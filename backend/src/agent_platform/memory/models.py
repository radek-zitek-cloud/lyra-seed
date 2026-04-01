"""Memory data models."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    """Type of memory entry."""

    # Cross-context (autobiographical)
    EPISODIC = "episodic"
    PREFERENCE = "preference"
    DECISION = "decision"
    OUTCOME = "outcome"
    # Long-term (factual/procedural)
    FACT = "fact"
    PROCEDURE = "procedure"
    TOOL_KNOWLEDGE = "tool_knowledge"
    DOMAIN_KNOWLEDGE = "domain_knowledge"


class MemoryEntry(BaseModel):
    """A single memory entry stored in the memory system."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    content: str
    memory_type: MemoryType
    importance: float = 0.5
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    last_accessed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    access_count: int = 0
    decay_score: float = 1.0
