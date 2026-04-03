"""Orchestration data models for task decomposition and execution."""

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class SubTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class OrchestrationStrategyType(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"


class FailurePolicy(StrEnum):
    RETRY = "retry"
    REASSIGN = "reassign"
    ESCALATE = "escalate"
    SKIP = "skip"


class SubTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    assigned_to: str  # tool name or "spawn_agent"
    dependencies: list[int] = Field(default_factory=list)
    status: SubTaskStatus = SubTaskStatus.PENDING
    result: str | None = None
    failure_policy: FailurePolicy = FailurePolicy.ESCALATE
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 2


class TaskPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    original_task: str
    subtasks: list[SubTask]
    strategy: OrchestrationStrategyType
    status: SubTaskStatus = SubTaskStatus.PENDING


class OrchestrationResult(BaseModel):
    plan_id: str
    results: dict[str, str]
    synthesized_response: str
    status: SubTaskStatus
