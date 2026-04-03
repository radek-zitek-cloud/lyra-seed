"""
Smoke tests for V2 Phase 6 — Orchestration Subtasks with Tool & Agent Execution.

All LLM calls are mocked — no real API calls.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.models import Agent, AgentConfig
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
from agent_platform.llm.models import LLMResponse
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.orchestration.models import (
    FailurePolicy,
    OrchestrationStrategyType,
    SubTask,
    SubTaskStatus,
    TaskPlan,
)
from agent_platform.orchestration.strategies import (
    ParallelOrchestration,
    PipelineOrchestration,
    SequentialOrchestration,
    _execute_subtask,
)
from agent_platform.tools.agent_spawner import AgentSpawnerProvider
from agent_platform.tools.models import Tool, ToolResult, ToolType
from agent_platform.tools.registry import ToolRegistry

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v2-phase-6"),
]


@pytest.fixture
async def deps(tmp_path):
    """Shared test dependencies."""
    agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
    conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
    msg_repo = SqliteMessageRepo(str(tmp_path / "msgs.db"))
    event_bus = InProcessEventBus(db_path=str(tmp_path / "events.db"))
    await agent_repo.initialize()
    await conv_repo.initialize()
    await msg_repo.initialize()
    await event_bus.initialize()

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="LLM result", usage={"prompt_tokens": 10, "completion_tokens": 5}
    )

    tool_registry = ToolRegistry()

    spawner = AgentSpawnerProvider(
        agent_repo=agent_repo,
        conversation_repo=conv_repo,
        llm_provider=mock_llm,
        event_bus=event_bus,
        tool_registry=tool_registry,
        message_repo=msg_repo,
    )
    tool_registry.register_provider(spawner)

    parent = Agent(name="orchestrator", config=AgentConfig(model="test-model"))
    await agent_repo.create(parent)

    yield {
        "agent_repo": agent_repo,
        "conv_repo": conv_repo,
        "msg_repo": msg_repo,
        "event_bus": event_bus,
        "llm": mock_llm,
        "tool_registry": tool_registry,
        "spawner": spawner,
        "parent": parent,
    }

    await spawner.cancel_all_tasks()
    await asyncio.sleep(0.2)
    await agent_repo.close()
    await conv_repo.close()
    await msg_repo.close()
    await event_bus.close()


class TestV2Phase6:
    """ST-V2-6.x: Orchestration subtask dispatch smoke tests."""

    @pytest.mark.asyncio
    async def test_st_v2_6_1_llm_fallback(self, deps):
        """ST-V2-6.1: assigned_to 'llm' uses direct LLM call (backward compat)."""
        subtask = SubTask(id="st-1", description="Summarize text", assigned_to="llm")

        result = await _execute_subtask(
            subtask=subtask,
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            tool_registry=deps["tool_registry"],
            agent_spawner=deps["spawner"],
        )

        assert result == "LLM result"
        assert subtask.status == SubTaskStatus.COMPLETED
        deps["llm"].complete.assert_called()

    @pytest.mark.asyncio
    async def test_st_v2_6_2_tool_dispatch(self, deps):
        """ST-V2-6.2: assigned_to matching a tool name calls the tool."""
        # Register a mock tool provider with a "test_tool" tool
        mock_provider = AsyncMock()
        mock_provider.list_tools.return_value = [
            Tool(
                name="test_tool",
                description="A test tool",
                input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
                tool_type=ToolType.MCP,
                source="test",
            )
        ]
        mock_provider.call_tool.return_value = ToolResult(
            success=True, output="Tool output: processed"
        )
        deps["tool_registry"].register_provider(mock_provider)

        # LLM extracts arguments
        deps["llm"].complete.return_value = LLMResponse(
            content='{"input": "hello"}', usage={}
        )

        subtask = SubTask(id="st-1", description="Process data", assigned_to="test_tool")

        result = await _execute_subtask(
            subtask=subtask,
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            tool_registry=deps["tool_registry"],
            agent_spawner=deps["spawner"],
        )

        assert "Tool output" in result
        assert subtask.status == SubTaskStatus.COMPLETED
        mock_provider.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_st_v2_6_3_agent_dispatch(self, deps):
        """ST-V2-6.3: assigned_to 'spawn_agent' spawns and waits for child."""
        # Mock LLM to return a response for the child agent
        deps["llm"].complete.return_value = LLMResponse(
            content="Child agent result", usage={}
        )

        subtask = SubTask(
            id="st-1", description="Research AI trends", assigned_to="spawn_agent"
        )

        result = await _execute_subtask(
            subtask=subtask,
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            tool_registry=deps["tool_registry"],
            agent_spawner=deps["spawner"],
        )

        assert result is not None
        assert len(result) > 0
        assert subtask.status == SubTaskStatus.COMPLETED

        # Verify a child agent was created
        children = await deps["agent_repo"].list(
            filters={"parent_agent_id": deps["parent"].id}
        )
        assert len(children) >= 1

    @pytest.mark.asyncio
    async def test_st_v2_6_4_unknown_fallback(self, deps):
        """ST-V2-6.4: Unknown assigned_to falls back to LLM."""
        subtask = SubTask(
            id="st-1", description="Do something", assigned_to="nonexistent_thing"
        )

        result = await _execute_subtask(
            subtask=subtask,
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            tool_registry=deps["tool_registry"],
            agent_spawner=deps["spawner"],
        )

        assert result == "LLM result"
        assert subtask.status == SubTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_st_v2_6_5_sequential_mixed_types(self, deps):
        """ST-V2-6.5: Sequential strategy with mixed subtask types."""
        # Register a mock tool
        mock_provider = AsyncMock()
        mock_provider.list_tools.return_value = [
            Tool(
                name="mock_tool",
                description="Mock",
                input_schema={"type": "object", "properties": {}},
                tool_type=ToolType.MCP,
                source="test",
            )
        ]
        mock_provider.call_tool.return_value = ToolResult(
            success=True, output="Tool result"
        )
        deps["tool_registry"].register_provider(mock_provider)

        call_count = 0

        async def multi_response(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            # First call: arg extraction for tool, second: LLM subtask,
            # third+: agent subtask
            return LLMResponse(content=f"LLM call {call_count}", usage={})

        deps["llm"].complete.side_effect = multi_response

        plan = TaskPlan(
            original_task="Mixed test",
            subtasks=[
                SubTask(id="st-1", description="LLM task", assigned_to="llm"),
                SubTask(id="st-2", description="Tool task", assigned_to="mock_tool"),
                SubTask(id="st-3", description="Agent task", assigned_to="spawn_agent"),
            ],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )

        strategy = SequentialOrchestration(
            llm_provider=deps["llm"],
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            agent_spawner=deps["spawner"],
        )

        result = await strategy.execute(plan)

        for st in plan.subtasks:
            assert st.status == SubTaskStatus.COMPLETED
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_st_v2_6_6_parallel_mixed_types(self, deps):
        """ST-V2-6.6: Parallel strategy with mixed subtask types."""
        mock_provider = AsyncMock()
        mock_provider.list_tools.return_value = [
            Tool(
                name="par_tool",
                description="Parallel tool",
                input_schema={"type": "object", "properties": {}},
                tool_type=ToolType.MCP,
                source="test",
            )
        ]
        mock_provider.call_tool.return_value = ToolResult(
            success=True, output="Par tool result"
        )
        deps["tool_registry"].register_provider(mock_provider)

        deps["llm"].complete.return_value = LLMResponse(content="Parallel LLM", usage={})

        plan = TaskPlan(
            original_task="Parallel mixed",
            subtasks=[
                SubTask(id="st-1", description="LLM", assigned_to="llm"),
                SubTask(id="st-2", description="Tool", assigned_to="par_tool"),
                SubTask(id="st-3", description="Agent", assigned_to="spawn_agent"),
            ],
            strategy=OrchestrationStrategyType.PARALLEL,
        )

        strategy = ParallelOrchestration(
            llm_provider=deps["llm"],
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            agent_spawner=deps["spawner"],
        )

        result = await strategy.execute(plan)

        for st in plan.subtasks:
            assert st.status == SubTaskStatus.COMPLETED
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_st_v2_6_7_pipeline_context_across_types(self, deps):
        """ST-V2-6.7: Pipeline passes context across execution modes."""
        received_descriptions = []
        call_count = 0

        async def track_llm(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            context = " ".join(str(m.content) for m in messages)
            received_descriptions.append(context)
            return LLMResponse(content=f"Stage {call_count} output", usage={})

        deps["llm"].complete.side_effect = track_llm

        plan = TaskPlan(
            original_task="Pipeline test",
            subtasks=[
                SubTask(id="st-1", description="Stage 1: gather", assigned_to="llm"),
                SubTask(id="st-2", description="Stage 2: process", assigned_to="llm"),
                SubTask(id="st-3", description="Stage 3: format", assigned_to="spawn_agent"),
            ],
            strategy=OrchestrationStrategyType.PIPELINE,
        )

        strategy = PipelineOrchestration(
            llm_provider=deps["llm"],
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            agent_spawner=deps["spawner"],
        )

        result = await strategy.execute(plan)

        for st in plan.subtasks:
            assert st.status == SubTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_st_v2_6_8_retry_tool_failure(self, deps):
        """ST-V2-6.8: Failure policy retry works for tool subtask."""
        mock_provider = AsyncMock()
        mock_provider.list_tools.return_value = [
            Tool(
                name="flaky_tool",
                description="Flaky",
                input_schema={"type": "object", "properties": {}},
                tool_type=ToolType.MCP,
                source="test",
            )
        ]
        tool_call_count = 0

        async def flaky_tool(name, args):
            nonlocal tool_call_count
            tool_call_count += 1
            if tool_call_count == 1:
                return ToolResult(success=False, error="Temporary failure")
            return ToolResult(success=True, output="Success on retry")

        mock_provider.call_tool.side_effect = flaky_tool
        deps["tool_registry"].register_provider(mock_provider)

        deps["llm"].complete.return_value = LLMResponse(content="{}", usage={})

        subtask = SubTask(
            id="st-1",
            description="Flaky task",
            assigned_to="flaky_tool",
            failure_policy=FailurePolicy.RETRY,
        )

        plan = TaskPlan(
            original_task="Retry test",
            subtasks=[subtask],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )

        strategy = SequentialOrchestration(
            llm_provider=deps["llm"],
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            agent_spawner=deps["spawner"],
        )

        await strategy.execute(plan)

        assert tool_call_count >= 2
        assert subtask.status == SubTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_st_v2_6_9_skip_agent_failure(self, deps):
        """ST-V2-6.9: Failure policy skip works for agent subtask."""
        # Make LLM raise on the agent subtask execution
        call_count = 0

        async def fail_on_agent(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First calls are for the spawn_agent subtask — make it fail
                raise Exception("Agent spawn failed")
            return LLMResponse(content="Second task done", usage={})

        deps["llm"].complete.side_effect = fail_on_agent

        plan = TaskPlan(
            original_task="Skip test",
            subtasks=[
                SubTask(
                    id="st-1",
                    description="Failing agent task",
                    assigned_to="spawn_agent",
                    failure_policy=FailurePolicy.SKIP,
                ),
                SubTask(
                    id="st-2",
                    description="LLM task",
                    assigned_to="llm",
                ),
            ],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )

        strategy = SequentialOrchestration(
            llm_provider=deps["llm"],
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            agent_spawner=deps["spawner"],
        )

        await strategy.execute(plan)

        assert plan.subtasks[0].status == SubTaskStatus.SKIPPED
        assert plan.subtasks[1].status == SubTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_st_v2_6_10_tool_arg_extraction(self, deps):
        """ST-V2-6.10: LLM extracts structured args from subtask description."""
        mock_provider = AsyncMock()
        mock_provider.list_tools.return_value = [
            Tool(
                name="list_files",
                description="List directory contents",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
                tool_type=ToolType.MCP,
                source="test",
            )
        ]
        mock_provider.call_tool.return_value = ToolResult(
            success=True, output="file1.txt\nfile2.txt"
        )
        deps["tool_registry"].register_provider(mock_provider)

        # LLM returns extracted args
        deps["llm"].complete.return_value = LLMResponse(
            content='{"path": "/home"}', usage={}
        )

        subtask = SubTask(
            id="st-1",
            description="List files in /home",
            assigned_to="list_files",
        )

        result = await _execute_subtask(
            subtask=subtask,
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            tool_registry=deps["tool_registry"],
            agent_spawner=deps["spawner"],
        )

        assert "file1.txt" in result
        # Verify LLM was called to extract args
        deps["llm"].complete.assert_called()
        # Verify tool was called with extracted args
        call_args = mock_provider.call_tool.call_args
        assert call_args[0][0] == "list_files"
        assert call_args[0][1]["path"] == "/home"

    @pytest.mark.asyncio
    async def test_st_v2_6_11_agent_inherits_parent_config(self, deps):
        """ST-V2-6.11: Spawned agent subtask inherits parent config."""
        deps["llm"].complete.return_value = LLMResponse(
            content="Child result", usage={}
        )

        subtask = SubTask(
            id="st-1", description="Research task", assigned_to="spawn_agent"
        )

        await _execute_subtask(
            subtask=subtask,
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
            tool_registry=deps["tool_registry"],
            agent_spawner=deps["spawner"],
        )

        # Check child agent was created with parent's model
        children = await deps["agent_repo"].list(
            filters={"parent_agent_id": deps["parent"].id}
        )
        assert len(children) >= 1
        child = children[0]
        assert child.config.model == deps["parent"].config.model
