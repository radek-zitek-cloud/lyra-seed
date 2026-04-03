"""Orchestration tool provider — exposes decompose_task and orchestrate as tools."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.llm.provider import LLMProvider
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.orchestration.decomposer import TaskDecomposer
from agent_platform.orchestration.models import (
    OrchestrationStrategyType,
    SubTaskStatus,
)
from agent_platform.orchestration.strategies import (
    ParallelOrchestration,
    PipelineOrchestration,
    SequentialOrchestration,
)
from agent_platform.orchestration.synthesizer import ResultSynthesizer
from agent_platform.tools.models import Tool, ToolResult, ToolType
from agent_platform.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from agent_platform.tools.agent_spawner import AgentSpawnerProvider

logger = logging.getLogger(__name__)


class OrchestrationToolProvider:
    """ToolProvider exposing orchestration capabilities as agent tools."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        agent_repo: SqliteAgentRepo,
        conversation_repo: SqliteConversationRepo,
        event_bus: InProcessEventBus,
        decompose_prompt: str | None = None,
        synthesize_prompt: str | None = None,
        agent_spawner: AgentSpawnerProvider | None = None,
        orchestration_temperature: float = 0.3,
    ) -> None:
        self._llm = llm_provider
        self._tool_registry = tool_registry
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._event_bus = event_bus
        self._agent_spawner = agent_spawner
        self._temperature = orchestration_temperature
        self._decomposer = TaskDecomposer(
            system_prompt=decompose_prompt,
        )
        self._synthesizer = ResultSynthesizer(
            system_prompt=synthesize_prompt,
        )

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="decompose_task",
                description=(
                    "Break a complex task into subtasks with an execution plan."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": ("The complex task to decompose"),
                        },
                    },
                    "required": ["task"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="orchestration",
            ),
            Tool(
                name="orchestrate",
                description=(
                    "End-to-end orchestration: decompose, "
                    "execute, and synthesize results."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The complex task to orchestrate",
                        },
                        "strategy": {
                            "type": "string",
                            "enum": ["sequential", "parallel", "pipeline"],
                            "description": ("Override strategy (optional)"),
                        },
                    },
                    "required": ["task"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="orchestration",
            ),
        ]

    async def _resolve_agent_config(self, agent_id: str) -> tuple[str | None, int]:
        """Look up the calling agent's orchestration config.

        Returns (model, max_subtasks).
        """
        if agent_id == "system":
            return None, 10
        agent = await self._agent_repo.get(agent_id)
        if not agent:
            return None, 10
        model = agent.config.orchestration_model or agent.config.model
        return model, agent.config.max_subtasks

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        start = time.monotonic()
        if name == "decompose_task":
            return await self._decompose_task(arguments, start)
        elif name == "orchestrate":
            return await self._orchestrate(arguments, start)
        return ToolResult(
            success=False,
            error=f"Unknown tool: {name}",
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def _decompose_task(self, args: dict[str, Any], start: float) -> ToolResult:
        task = args["task"]
        agent_id = args.get("agent_id", "system")

        try:
            model, max_subtasks = await self._resolve_agent_config(
                agent_id,
            )
            tools = await self._tool_registry.list_tools()
            plan = await self._decomposer.decompose(
                task,
                tools,
                self._llm,
                model=model,
                max_subtasks=max_subtasks,
                temperature=self._temperature,
            )

            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.TOOL_RESULT,
                    module="orchestration.decompose",
                    payload={
                        "plan_id": plan.id,
                        "subtask_count": len(plan.subtasks),
                        "strategy": plan.strategy.value,
                    },
                )
            )

            return ToolResult(
                success=True,
                output=json.dumps(
                    {
                        "plan_id": plan.id,
                        "original_task": plan.original_task,
                        "strategy": plan.strategy.value,
                        "subtasks": [
                            {
                                "id": st.id,
                                "description": st.description,
                                "assigned_to": st.assigned_to,
                                "dependencies": st.dependencies,
                                "failure_policy": st.failure_policy.value,
                            }
                            for st in plan.subtasks
                        ],
                    }
                ),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            logger.exception("Task decomposition failed")
            return ToolResult(
                success=False,
                error=f"Decomposition failed: {e}",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def _orchestrate(self, args: dict[str, Any], start: float) -> ToolResult:
        task = args["task"]
        agent_id = args.get("agent_id", "system")
        strategy_override = args.get("strategy")

        try:
            # 1. Decompose
            model, max_subtasks = await self._resolve_agent_config(
                agent_id,
            )
            tools = await self._tool_registry.list_tools()
            plan = await self._decomposer.decompose(
                task,
                tools,
                self._llm,
                model=model,
                max_subtasks=max_subtasks,
                temperature=self._temperature,
            )

            if strategy_override:
                plan.strategy = OrchestrationStrategyType(strategy_override)

            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.TOOL_CALL,
                    module="orchestration.orchestrate",
                    payload={
                        "plan_id": plan.id,
                        "strategy": plan.strategy.value,
                        "subtask_count": len(plan.subtasks),
                        "task": task[:200],
                    },
                )
            )

            # 2. Execute via strategy
            strategy_kwargs = dict(
                llm_provider=self._llm,
                tool_registry=self._tool_registry,
                agent_repo=self._agent_repo,
                conversation_repo=self._conv_repo,
                event_bus=self._event_bus,
                parent_agent_id=agent_id,
                model=model,
                agent_spawner=self._agent_spawner,
            )

            if plan.strategy == OrchestrationStrategyType.SEQUENTIAL:
                strategy = SequentialOrchestration(**strategy_kwargs)
            elif plan.strategy == OrchestrationStrategyType.PARALLEL:
                strategy = ParallelOrchestration(**strategy_kwargs)
            elif plan.strategy == OrchestrationStrategyType.PIPELINE:
                strategy = PipelineOrchestration(**strategy_kwargs)
            else:
                strategy = SequentialOrchestration(**strategy_kwargs)

            orch_result = await strategy.execute(plan)

            # 3. Synthesize if execution succeeded
            if orch_result.status == SubTaskStatus.COMPLETED and orch_result.results:
                synthesized = await self._synthesizer.synthesize(
                    task,
                    orch_result.results,
                    self._llm,
                    model=model,
                    temperature=self._temperature,
                )
                orch_result.synthesized_response = synthesized

            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.TOOL_RESULT,
                    module="orchestration.orchestrate",
                    payload={
                        "plan_id": plan.id,
                        "status": orch_result.status.value,
                        "subtask_results": len(orch_result.results),
                    },
                )
            )

            return ToolResult(
                success=orch_result.status == SubTaskStatus.COMPLETED,
                output=json.dumps(
                    {
                        "plan_id": orch_result.plan_id,
                        "status": orch_result.status.value,
                        "synthesized_response": orch_result.synthesized_response,
                        "subtask_results": orch_result.results,
                    }
                ),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            logger.exception("Orchestration failed")
            return ToolResult(
                success=False,
                error=f"Orchestration failed: {e}",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
