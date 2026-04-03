"""Orchestration strategies — sequential, parallel, and pipeline execution."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from agent_platform.tools.agent_spawner import AgentSpawnerProvider

logger = logging.getLogger(__name__)


async def _execute_subtask(
    subtask: SubTask,
    llm_provider: LLMProvider,
    event_bus: InProcessEventBus,
    parent_agent_id: str,
    previous_output: str | None = None,
    model: str | None = None,
    tool_registry: ToolRegistry | None = None,
    agent_spawner: AgentSpawnerProvider | None = None,
) -> str:
    """Execute a single subtask, dispatching by assigned_to type."""
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

    # --- Dispatch based on assigned_to ---

    assigned = subtask.assigned_to

    if assigned == "spawn_agent" and agent_spawner is not None:
        result = await _execute_via_agent(
            subtask, agent_spawner, parent_agent_id, previous_output
        )
    elif (
        assigned not in ("llm", "spawn_agent")
        and tool_registry is not None
        and await _is_registered_tool(assigned, tool_registry)
    ):
        result = await _execute_via_tool(
            subtask, tool_registry, llm_provider, previous_output, model
        )
    else:
        # Default: direct LLM call (backward compatible)
        result = await _execute_via_llm(subtask, llm_provider, previous_output, model)

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


async def _is_registered_tool(name: str, tool_registry: ToolRegistry) -> bool:
    """Check if a tool name exists in the registry."""
    tools = await tool_registry.list_tools()
    return any(t.name == name for t in tools)


async def _execute_via_llm(
    subtask: SubTask,
    llm_provider: LLMProvider,
    previous_output: str | None = None,
    model: str | None = None,
) -> str:
    """Execute subtask as a direct LLM call (original behavior)."""
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

    messages.append(Message(role=MessageRole.HUMAN, content=subtask.description))

    config = LLMConfig(temperature=0.5)
    if model:
        config.model = model
    response = await llm_provider.complete(messages, config=config)
    return response.content or ""


async def _execute_via_tool(
    subtask: SubTask,
    tool_registry: ToolRegistry,
    llm_provider: LLMProvider,
    previous_output: str | None = None,
    model: str | None = None,
) -> str:
    """Execute subtask by calling a registered tool.

    Uses an LLM pre-call to extract structured arguments from the
    natural-language subtask description.
    """
    tool_name = subtask.assigned_to

    # Get the tool schema for argument extraction
    tools = await tool_registry.list_tools()
    tool = next((t for t in tools if t.name == tool_name), None)
    schema_str = json.dumps(tool.input_schema) if tool else "{}"

    # LLM extracts structured args from description
    prompt = (
        f"Extract the arguments for the tool '{tool_name}' "
        f"from this task description.\n"
        f"Tool schema: {schema_str}\n"
    )
    if previous_output:
        prompt += f"Context from previous stage:\n{previous_output}\n"
    prompt += (
        f"Task: {subtask.description}\n\n"
        "Return ONLY a JSON object with the arguments. No explanation."
    )

    config = LLMConfig(temperature=0.1)
    if model:
        config.model = model
    arg_response = await llm_provider.complete(
        [Message(role=MessageRole.HUMAN, content=prompt)], config=config
    )

    # Parse extracted args
    try:
        raw = arg_response.content or "{}"
        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        args = json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        args = {}

    # Call the tool
    tool_result = await tool_registry.call_tool(tool_name, args)
    if not tool_result.success:
        raise RuntimeError(f"Tool '{tool_name}' failed: {tool_result.error}")

    return tool_result.output or ""


async def _execute_via_agent(
    subtask: SubTask,
    agent_spawner: AgentSpawnerProvider,
    parent_agent_id: str,
    previous_output: str | None = None,
) -> str:
    """Execute subtask by spawning a child agent and waiting for its result."""
    task_prompt = subtask.description
    if previous_output:
        task_prompt = (
            f"Context from previous stage:\n{previous_output}\n\n"
            f"Task: {subtask.description}"
        )

    # Spawn child agent
    spawn_result = await agent_spawner.call_tool(
        "spawn_agent",
        {
            "name": f"subtask-{subtask.id[:8]}",
            "task": task_prompt,
            "agent_id": parent_agent_id,
        },
    )
    if not spawn_result.success:
        raise RuntimeError(f"Failed to spawn agent: {spawn_result.error}")

    spawn_data = json.loads(spawn_result.output)
    child_id = spawn_data["child_agent_id"]

    # Wait for child to complete
    wait_result = await agent_spawner.call_tool(
        "wait_for_agent",
        {
            "child_agent_id": child_id,
            "timeout": 300,
            "agent_id": parent_agent_id,
        },
    )

    if not wait_result.success:
        raise RuntimeError(f"Agent subtask failed: {wait_result.error}")

    # Extract child's response
    wait_data = json.loads(wait_result.output)
    return wait_data.get("content", wait_data.get("result", ""))


async def _handle_failure(
    subtask: SubTask,
    error: Exception,
    llm_provider: LLMProvider,
    event_bus: InProcessEventBus,
    parent_agent_id: str,
    previous_output: str | None = None,
    model: str | None = None,
    tool_registry: ToolRegistry | None = None,
    agent_spawner: AgentSpawnerProvider | None = None,
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
                subtask,
                llm_provider,
                event_bus,
                parent_agent_id,
                previous_output,
                model=model,
                tool_registry=tool_registry,
                agent_spawner=agent_spawner,
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
        logger.info(
            "Reassigning subtask %s to a new execution",
            subtask.id,
        )
        subtask.retry_count += 1
        subtask.status = SubTaskStatus.PENDING
        return await _execute_subtask(
            subtask,
            llm_provider,
            event_bus,
            parent_agent_id,
            previous_output,
            model=model,
            tool_registry=tool_registry,
            agent_spawner=agent_spawner,
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
        model: str | None = None,
        agent_spawner: AgentSpawnerProvider | None = None,
    ) -> None:
        self._llm = llm_provider
        self._tool_registry = tool_registry
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._event_bus = event_bus
        self._parent_agent_id = parent_agent_id
        self._model = model
        self._agent_spawner = agent_spawner

    async def execute(self, plan: TaskPlan) -> OrchestrationResult:
        plan.status = SubTaskStatus.RUNNING
        results: dict[str, str] = {}

        for subtask in plan.subtasks:
            try:
                result = await _execute_subtask(
                    subtask,
                    self._llm,
                    self._event_bus,
                    self._parent_agent_id,
                    model=self._model,
                    tool_registry=self._tool_registry,
                    agent_spawner=self._agent_spawner,
                )
                results[subtask.id] = result
            except Exception as e:
                recovered = await _handle_failure(
                    subtask,
                    e,
                    self._llm,
                    self._event_bus,
                    self._parent_agent_id,
                    model=self._model,
                    tool_registry=self._tool_registry,
                    agent_spawner=self._agent_spawner,
                )
                if recovered is not None:
                    results[subtask.id] = recovered
                elif subtask.status == SubTaskStatus.FAILED:
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
        model: str | None = None,
        agent_spawner: AgentSpawnerProvider | None = None,
    ) -> None:
        self._llm = llm_provider
        self._tool_registry = tool_registry
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._event_bus = event_bus
        self._parent_agent_id = parent_agent_id
        self._model = model
        self._agent_spawner = agent_spawner

    async def execute(self, plan: TaskPlan) -> OrchestrationResult:
        plan.status = SubTaskStatus.RUNNING
        results: dict[str, str] = {}

        async def run_subtask(subtask: SubTask) -> tuple[str, str | None]:
            try:
                result = await _execute_subtask(
                    subtask,
                    self._llm,
                    self._event_bus,
                    self._parent_agent_id,
                    model=self._model,
                    tool_registry=self._tool_registry,
                    agent_spawner=self._agent_spawner,
                )
                return subtask.id, result
            except Exception as e:
                recovered = await _handle_failure(
                    subtask,
                    e,
                    self._llm,
                    self._event_bus,
                    self._parent_agent_id,
                    model=self._model,
                    tool_registry=self._tool_registry,
                    agent_spawner=self._agent_spawner,
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
        model: str | None = None,
        agent_spawner: AgentSpawnerProvider | None = None,
    ) -> None:
        self._llm = llm_provider
        self._tool_registry = tool_registry
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._event_bus = event_bus
        self._parent_agent_id = parent_agent_id
        self._model = model
        self._agent_spawner = agent_spawner

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
                    model=self._model,
                    tool_registry=self._tool_registry,
                    agent_spawner=self._agent_spawner,
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
                    model=self._model,
                    tool_registry=self._tool_registry,
                    agent_spawner=self._agent_spawner,
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
                            f"Pipeline failed at: {subtask.description}"
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
