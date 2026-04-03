"""Orchestration strategies — sequential, parallel, and pipeline execution."""

import asyncio
import logging

from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.llm.models import LLMConfig, Message, MessageRole
from agent_platform.llm.provider import LLMProvider
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.orchestration.models import (
    FailurePolicy,
    OrchestrationResult,
    SubTask,
    SubTaskStatus,
    TaskPlan,
)
from agent_platform.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


async def _execute_subtask(
    subtask: SubTask,
    llm_provider: LLMProvider,
    event_bus: InProcessEventBus,
    parent_agent_id: str,
    previous_output: str | None = None,
) -> str:
    """Execute a single subtask using the LLM."""
    subtask.status = SubTaskStatus.RUNNING

    await event_bus.emit(
        Event(
            agent_id=parent_agent_id,
            event_type=EventType.TOOL_CALL,
            module="orchestration.strategy",
            payload={
                "subtask_id": subtask.id,
                "description": subtask.description,
                "assigned_to": subtask.assigned_to,
            },
        )
    )

    messages = [
        Message(
            role=MessageRole.SYSTEM,
            content=(
                "You are executing a subtask as part of "
                "a larger orchestrated plan. "
                "Complete the following task thoroughly."
            ),
        ),
    ]

    if previous_output:
        messages.append(
            Message(
                role=MessageRole.SYSTEM,
                content=f"Context from previous stage:\n{previous_output}",
            )
        )

    messages.append(
        Message(
            role=MessageRole.HUMAN,
            content=subtask.description,
        )
    )

    response = await llm_provider.complete(messages, config=LLMConfig(temperature=0.5))
    result = response.content or ""

    subtask.status = SubTaskStatus.COMPLETED
    subtask.result = result

    await event_bus.emit(
        Event(
            agent_id=parent_agent_id,
            event_type=EventType.TOOL_RESULT,
            module="orchestration.strategy",
            payload={
                "subtask_id": subtask.id,
                "status": subtask.status.value,
                "result_preview": result[:200],
            },
        )
    )

    return result


async def _handle_failure(
    subtask: SubTask,
    error: Exception,
    llm_provider: LLMProvider,
    event_bus: InProcessEventBus,
    parent_agent_id: str,
    previous_output: str | None = None,
) -> str | None:
    """Apply failure policy to a failed subtask. Returns result if recovered."""
    subtask.error = str(error)

    if subtask.failure_policy == FailurePolicy.RETRY:
        subtask.retry_count += 1
        if subtask.retry_count <= subtask.max_retries:
            logger.info(
                "Retrying subtask %s (attempt %d/%d)",
                subtask.id,
                subtask.retry_count,
                subtask.max_retries,
            )
            subtask.status = SubTaskStatus.PENDING
            return await _execute_subtask(
                subtask, llm_provider, event_bus, parent_agent_id, previous_output
            )
        # Exhausted retries
        subtask.status = SubTaskStatus.FAILED
        return None

    elif subtask.failure_policy == FailurePolicy.SKIP:
        logger.info("Skipping failed subtask %s", subtask.id)
        subtask.status = SubTaskStatus.SKIPPED
        subtask.result = f"[SKIPPED: {error}]"
        return subtask.result

    elif subtask.failure_policy == FailurePolicy.REASSIGN:
        logger.info("Reassigning subtask %s to a new execution", subtask.id)
        subtask.retry_count += 1
        subtask.status = SubTaskStatus.PENDING
        return await _execute_subtask(
            subtask, llm_provider, event_bus, parent_agent_id, previous_output
        )

    else:  # ESCALATE
        subtask.status = SubTaskStatus.FAILED
        return None


class SequentialOrchestration:
    """Runs subtasks one by one in order."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        agent_repo: SqliteAgentRepo,
        conversation_repo: SqliteConversationRepo,
        event_bus: InProcessEventBus,
        parent_agent_id: str,
    ) -> None:
        self._llm = llm_provider
        self._tool_registry = tool_registry
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._event_bus = event_bus
        self._parent_agent_id = parent_agent_id

    async def execute(self, plan: TaskPlan) -> OrchestrationResult:
        plan.status = SubTaskStatus.RUNNING
        results: dict[str, str] = {}

        for subtask in plan.subtasks:
            try:
                result = await _execute_subtask(
                    subtask, self._llm, self._event_bus, self._parent_agent_id
                )
                results[subtask.id] = result
            except Exception as e:
                recovered = await _handle_failure(
                    subtask, e, self._llm, self._event_bus, self._parent_agent_id
                )
                if recovered is not None:
                    results[subtask.id] = recovered
                elif subtask.status == SubTaskStatus.FAILED:
                    # ESCALATE — stop orchestration
                    plan.status = SubTaskStatus.FAILED
                    return OrchestrationResult(
                        plan_id=plan.id,
                        results=results,
                        synthesized_response=(
                            f"Orchestration failed: "
                            f"subtask '{subtask.description}'"
                            f" failed: {e}"
                        ),
                        status=SubTaskStatus.FAILED,
                    )

        plan.status = SubTaskStatus.COMPLETED
        return OrchestrationResult(
            plan_id=plan.id,
            results=results,
            synthesized_response="",
            status=SubTaskStatus.COMPLETED,
        )


class ParallelOrchestration:
    """Runs independent subtasks concurrently."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        agent_repo: SqliteAgentRepo,
        conversation_repo: SqliteConversationRepo,
        event_bus: InProcessEventBus,
        parent_agent_id: str,
    ) -> None:
        self._llm = llm_provider
        self._tool_registry = tool_registry
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._event_bus = event_bus
        self._parent_agent_id = parent_agent_id

    async def execute(self, plan: TaskPlan) -> OrchestrationResult:
        plan.status = SubTaskStatus.RUNNING
        results: dict[str, str] = {}

        async def run_subtask(subtask: SubTask) -> tuple[str, str | None]:
            try:
                result = await _execute_subtask(
                    subtask, self._llm, self._event_bus, self._parent_agent_id
                )
                return subtask.id, result
            except Exception as e:
                recovered = await _handle_failure(
                    subtask, e, self._llm, self._event_bus, self._parent_agent_id
                )
                return subtask.id, recovered

        task_results = await asyncio.gather(*(run_subtask(st) for st in plan.subtasks))

        failed = False
        for subtask_id, result in task_results:
            if result is not None:
                results[subtask_id] = result
            else:
                failed = True

        status = SubTaskStatus.FAILED if failed else SubTaskStatus.COMPLETED
        plan.status = status
        return OrchestrationResult(
            plan_id=plan.id,
            results=results,
            synthesized_response="" if not failed else "Some subtasks failed",
            status=status,
        )


class PipelineOrchestration:
    """Chains subtasks so output of one becomes input context for the next."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        agent_repo: SqliteAgentRepo,
        conversation_repo: SqliteConversationRepo,
        event_bus: InProcessEventBus,
        parent_agent_id: str,
    ) -> None:
        self._llm = llm_provider
        self._tool_registry = tool_registry
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._event_bus = event_bus
        self._parent_agent_id = parent_agent_id

    async def execute(self, plan: TaskPlan) -> OrchestrationResult:
        plan.status = SubTaskStatus.RUNNING
        results: dict[str, str] = {}
        previous_output: str | None = None

        for subtask in plan.subtasks:
            try:
                result = await _execute_subtask(
                    subtask,
                    self._llm,
                    self._event_bus,
                    self._parent_agent_id,
                    previous_output=previous_output,
                )
                results[subtask.id] = result
                previous_output = result
            except Exception as e:
                recovered = await _handle_failure(
                    subtask,
                    e,
                    self._llm,
                    self._event_bus,
                    self._parent_agent_id,
                    previous_output=previous_output,
                )
                if recovered is not None:
                    results[subtask.id] = recovered
                    previous_output = recovered
                elif subtask.status == SubTaskStatus.FAILED:
                    plan.status = SubTaskStatus.FAILED
                    return OrchestrationResult(
                        plan_id=plan.id,
                        results=results,
                        synthesized_response=(
                            f"Pipeline failed at: "
                            f"{subtask.description}"
                        ),
                        status=SubTaskStatus.FAILED,
                    )

        plan.status = SubTaskStatus.COMPLETED
        return OrchestrationResult(
            plan_id=plan.id,
            results=results,
            synthesized_response="",
            status=SubTaskStatus.COMPLETED,
        )
