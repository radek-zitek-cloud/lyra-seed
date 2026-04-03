"""
Smoke tests for V2 Phase 3 — Orchestration Patterns.

All LLM calls are mocked — no real API calls.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest

from agent_platform.core.models import Agent, AgentConfig
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_message_repo import SqliteMessageRepo
from agent_platform.llm.models import LLMResponse
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.agent_spawner import AgentSpawnerProvider
from agent_platform.tools.registry import ToolRegistry

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v2-phase-3"),
]


@pytest.fixture
async def deps(tmp_path):
    """Set up shared test dependencies for orchestration tests."""
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
        content="Done", usage={"prompt_tokens": 10, "completion_tokens": 5}
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

    # Create a parent agent for orchestration
    parent = Agent(name="orchestrator", config=AgentConfig(model="test"))
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
        "tmp_path": tmp_path,
    }

    # Cleanup
    await spawner.cancel_all_tasks()
    await asyncio.sleep(0.2)
    await agent_repo.close()
    await conv_repo.close()
    await msg_repo.close()
    await event_bus.close()


class TestV2Phase3:
    """ST-V2-3.x: Orchestration Patterns smoke tests."""

    def test_st_v2_3_1_orchestration_models(self):
        """ST-V2-3.1: Orchestration models exist with correct fields."""
        from agent_platform.orchestration.models import (
            FailurePolicy,
            OrchestrationResult,
            OrchestrationStrategyType,
            SubTask,
            SubTaskStatus,
            TaskPlan,
        )

        # SubTaskStatus enum
        assert SubTaskStatus.PENDING == "pending"
        assert SubTaskStatus.RUNNING == "running"
        assert SubTaskStatus.COMPLETED == "completed"
        assert SubTaskStatus.FAILED == "failed"
        assert SubTaskStatus.SKIPPED == "skipped"

        # OrchestrationStrategyType enum
        assert OrchestrationStrategyType.SEQUENTIAL == "sequential"
        assert OrchestrationStrategyType.PARALLEL == "parallel"
        assert OrchestrationStrategyType.PIPELINE == "pipeline"

        # FailurePolicy enum
        assert FailurePolicy.RETRY == "retry"
        assert FailurePolicy.REASSIGN == "reassign"
        assert FailurePolicy.ESCALATE == "escalate"
        assert FailurePolicy.SKIP == "skip"

        # SubTask model
        st = SubTask(
            description="Write tests",
            assigned_to="spawn_agent",
        )
        assert st.id is not None
        assert st.description == "Write tests"
        assert st.assigned_to == "spawn_agent"
        assert st.dependencies == []
        assert st.status == SubTaskStatus.PENDING
        assert st.result is None
        assert st.failure_policy == FailurePolicy.ESCALATE

        # TaskPlan model
        plan = TaskPlan(
            original_task="Build a web app",
            subtasks=[st],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )
        assert plan.id is not None
        assert plan.original_task == "Build a web app"
        assert len(plan.subtasks) == 1
        assert plan.strategy == OrchestrationStrategyType.SEQUENTIAL
        assert plan.status == SubTaskStatus.PENDING

        # OrchestrationResult model
        result = OrchestrationResult(
            plan_id=plan.id,
            results={"st-1": "done"},
            synthesized_response="All done.",
            status=SubTaskStatus.COMPLETED,
        )
        assert result.plan_id == plan.id
        assert result.results == {"st-1": "done"}
        assert result.synthesized_response == "All done."
        assert result.status == SubTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_st_v2_3_2_task_decomposition(self, deps):
        """ST-V2-3.2: Task decomposition produces a valid plan."""
        from agent_platform.orchestration.decomposer import TaskDecomposer
        from agent_platform.orchestration.models import (
            OrchestrationStrategyType,
            SubTaskStatus,
        )

        mock_llm = deps["llm"]
        # Mock LLM to return a structured decomposition
        decomposition_json = json.dumps(
            {
                "subtasks": [
                    {
                        "description": "Research the topic",
                        "assigned_to": "spawn_agent",
                        "failure_policy": "retry",
                    },
                    {
                        "description": "Write the report",
                        "assigned_to": "spawn_agent",
                        "dependencies": [0],
                        "failure_policy": "escalate",
                    },
                    {
                        "description": "Review the report",
                        "assigned_to": "spawn_agent",
                        "dependencies": [1],
                        "failure_policy": "skip",
                    },
                ],
                "strategy": "sequential",
            }
        )
        mock_llm.complete.return_value = LLMResponse(
            content=decomposition_json, usage={}
        )

        decomposer = TaskDecomposer()
        tools = await deps["tool_registry"].list_tools()
        plan = await decomposer.decompose(
            task="Write a research report on AI",
            available_tools=tools,
            llm=mock_llm,
        )

        assert plan.original_task == "Write a research report on AI"
        assert len(plan.subtasks) == 3
        assert plan.strategy == OrchestrationStrategyType.SEQUENTIAL
        for st in plan.subtasks:
            assert st.status == SubTaskStatus.PENDING
            assert st.description
            assert st.assigned_to

    @pytest.mark.asyncio
    async def test_st_v2_3_3_sequential_orchestration(self, deps):
        """ST-V2-3.3: Sequential orchestration runs subtasks in order."""
        from agent_platform.orchestration.models import (
            OrchestrationStrategyType,
            SubTask,
            SubTaskStatus,
            TaskPlan,
        )
        from agent_platform.orchestration.strategies import SequentialOrchestration

        execution_order = []
        mock_llm = deps["llm"]

        async def track_execution(*a, **kw):
            execution_order.append(len(execution_order) + 1)
            return LLMResponse(content=f"Result {len(execution_order)}", usage={})

        mock_llm.complete.side_effect = track_execution

        plan = TaskPlan(
            original_task="Test sequential",
            subtasks=[
                SubTask(id="st-1", description="Step 1", assigned_to="spawn_agent"),
                SubTask(id="st-2", description="Step 2", assigned_to="spawn_agent"),
                SubTask(id="st-3", description="Step 3", assigned_to="spawn_agent"),
            ],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )

        strategy = SequentialOrchestration(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
        )

        result = await strategy.execute(plan)

        # All executed in order
        assert execution_order == [1, 2, 3]
        # All subtasks completed
        for st in plan.subtasks:
            assert st.status == SubTaskStatus.COMPLETED
        # Results collected
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_st_v2_3_4_parallel_orchestration(self, deps):
        """ST-V2-3.4: Parallel orchestration runs independent subtasks concurrently."""
        from agent_platform.orchestration.models import (
            OrchestrationStrategyType,
            SubTask,
            SubTaskStatus,
            TaskPlan,
        )
        from agent_platform.orchestration.strategies import ParallelOrchestration

        start_times = {}
        mock_llm = deps["llm"]

        async def slow_execution(*a, **kw):
            task_id = id(asyncio.current_task())
            start_times[task_id] = time.monotonic()
            await asyncio.sleep(0.2)
            return LLMResponse(content="Parallel result", usage={})

        mock_llm.complete.side_effect = slow_execution

        plan = TaskPlan(
            original_task="Test parallel",
            subtasks=[
                SubTask(id="st-1", description="Task A", assigned_to="spawn_agent"),
                SubTask(id="st-2", description="Task B", assigned_to="spawn_agent"),
                SubTask(id="st-3", description="Task C", assigned_to="spawn_agent"),
            ],
            strategy=OrchestrationStrategyType.PARALLEL,
        )

        strategy = ParallelOrchestration(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
        )

        start = time.monotonic()
        result = await strategy.execute(plan)
        elapsed = time.monotonic() - start

        # All completed
        for st in plan.subtasks:
            assert st.status == SubTaskStatus.COMPLETED
        assert len(result.results) == 3

        # Should be roughly parallel — total time near 0.2s, not 0.6s
        assert elapsed < 0.5  # generous margin, but less than 3x sequential

    @pytest.mark.asyncio
    async def test_st_v2_3_5_pipeline_orchestration(self, deps):
        """ST-V2-3.5: Pipeline orchestration chains output to input."""
        from agent_platform.orchestration.models import (
            OrchestrationStrategyType,
            SubTask,
            SubTaskStatus,
            TaskPlan,
        )
        from agent_platform.orchestration.strategies import PipelineOrchestration

        received_contexts = []
        mock_llm = deps["llm"]
        call_count = 0

        async def pipeline_execution(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            # Capture what context was passed
            context_str = " ".join(str(m.content) for m in messages)
            received_contexts.append(context_str)
            return LLMResponse(content=f"Stage {call_count} output", usage={})

        mock_llm.complete.side_effect = pipeline_execution

        plan = TaskPlan(
            original_task="Test pipeline",
            subtasks=[
                SubTask(
                    id="st-1",
                    description="Stage 1: gather data",
                    assigned_to="spawn_agent",
                ),
                SubTask(
                    id="st-2",
                    description="Stage 2: process data",
                    assigned_to="spawn_agent",
                ),
                SubTask(
                    id="st-3",
                    description="Stage 3: format output",
                    assigned_to="spawn_agent",
                ),
            ],
            strategy=OrchestrationStrategyType.PIPELINE,
        )

        strategy = PipelineOrchestration(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
        )

        await strategy.execute(plan)

        # All completed
        for st in plan.subtasks:
            assert st.status == SubTaskStatus.COMPLETED

        # Stage 2 should have received Stage 1's output in its context
        assert len(received_contexts) == 3
        # Stage 2 context should reference Stage 1 output
        assert "Stage 1 output" in received_contexts[1]
        # Stage 3 context should reference Stage 2 output
        assert "Stage 2 output" in received_contexts[2]

    @pytest.mark.asyncio
    async def test_st_v2_3_6_result_synthesis(self, deps):
        """ST-V2-3.6: Result synthesis combines subtask outputs."""
        from agent_platform.orchestration.synthesizer import ResultSynthesizer

        mock_llm = deps["llm"]
        mock_llm.complete.return_value = LLMResponse(
            content="Here is the unified report combining all findings.",
            usage={},
        )

        synthesizer = ResultSynthesizer()
        result = await synthesizer.synthesize(
            original_task="Write a comprehensive report",
            results={
                "st-1": "Research findings: AI is growing rapidly",
                "st-2": "Analysis: adoption rates increasing 30% yearly",
                "st-3": "Conclusion: significant market opportunity",
            },
            llm=mock_llm,
        )

        assert isinstance(result, str)
        assert len(result) > 0

        # Verify LLM was called with all results
        call_args = mock_llm.complete.call_args
        messages = call_args[0][0]
        prompt_text = " ".join(str(m.content) for m in messages)
        assert "Research findings" in prompt_text
        assert "Analysis" in prompt_text
        assert "Conclusion" in prompt_text
        assert "Write a comprehensive report" in prompt_text

    @pytest.mark.asyncio
    async def test_st_v2_3_7_failure_policy_retry(self, deps):
        """ST-V2-3.7: Failure policy RETRY retries failed subtask."""
        from agent_platform.orchestration.models import (
            FailurePolicy,
            OrchestrationStrategyType,
            SubTask,
            SubTaskStatus,
            TaskPlan,
        )
        from agent_platform.orchestration.strategies import SequentialOrchestration

        mock_llm = deps["llm"]
        call_count = 0

        async def fail_then_succeed(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            return LLMResponse(content="Success on retry", usage={})

        mock_llm.complete.side_effect = fail_then_succeed

        plan = TaskPlan(
            original_task="Test retry",
            subtasks=[
                SubTask(
                    id="st-1",
                    description="Flaky task",
                    assigned_to="spawn_agent",
                    failure_policy=FailurePolicy.RETRY,
                ),
            ],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )

        strategy = SequentialOrchestration(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
        )

        await strategy.execute(plan)

        assert call_count >= 2  # Retried
        assert plan.subtasks[0].status == SubTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_st_v2_3_8_failure_policy_skip(self, deps):
        """ST-V2-3.8: Failure policy SKIP skips failed subtask."""
        from agent_platform.orchestration.models import (
            FailurePolicy,
            OrchestrationStrategyType,
            SubTask,
            SubTaskStatus,
            TaskPlan,
        )
        from agent_platform.orchestration.strategies import SequentialOrchestration

        mock_llm = deps["llm"]
        call_count = 0

        async def fail_on_first(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Non-critical failure")
            return LLMResponse(content="Second task done", usage={})

        mock_llm.complete.side_effect = fail_on_first

        plan = TaskPlan(
            original_task="Test skip",
            subtasks=[
                SubTask(
                    id="st-1",
                    description="Optional task",
                    assigned_to="spawn_agent",
                    failure_policy=FailurePolicy.SKIP,
                ),
                SubTask(
                    id="st-2",
                    description="Required task",
                    assigned_to="spawn_agent",
                    failure_policy=FailurePolicy.ESCALATE,
                ),
            ],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )

        strategy = SequentialOrchestration(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
        )

        await strategy.execute(plan)

        assert plan.subtasks[0].status == SubTaskStatus.SKIPPED
        assert plan.subtasks[1].status == SubTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_st_v2_3_9_failure_policy_escalate(self, deps):
        """ST-V2-3.9: Failure policy ESCALATE stops orchestration."""
        from agent_platform.orchestration.models import (
            FailurePolicy,
            OrchestrationStrategyType,
            SubTask,
            SubTaskStatus,
            TaskPlan,
        )
        from agent_platform.orchestration.strategies import SequentialOrchestration

        mock_llm = deps["llm"]
        mock_llm.complete.side_effect = Exception("Critical failure")

        plan = TaskPlan(
            original_task="Test escalate",
            subtasks=[
                SubTask(
                    id="st-1",
                    description="Critical task",
                    assigned_to="spawn_agent",
                    failure_policy=FailurePolicy.ESCALATE,
                ),
                SubTask(
                    id="st-2",
                    description="Should not run",
                    assigned_to="spawn_agent",
                ),
            ],
            strategy=OrchestrationStrategyType.SEQUENTIAL,
        )

        strategy = SequentialOrchestration(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
            parent_agent_id=deps["parent"].id,
        )

        result = await strategy.execute(plan)

        assert plan.subtasks[0].status == SubTaskStatus.FAILED
        assert plan.subtasks[1].status == SubTaskStatus.PENDING  # Never ran
        assert result.status == SubTaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_st_v2_3_10_decompose_task_tool(self, deps):
        """ST-V2-3.10: decompose_task tool is callable via ToolRegistry."""
        from agent_platform.orchestration.tool_provider import (
            OrchestrationToolProvider,
        )

        mock_llm = deps["llm"]
        decomposition_json = json.dumps(
            {
                "subtasks": [
                    {
                        "description": "Step 1",
                        "assigned_to": "spawn_agent",
                    },
                ],
                "strategy": "sequential",
            }
        )
        mock_llm.complete.return_value = LLMResponse(
            content=decomposition_json, usage={}
        )

        orch_provider = OrchestrationToolProvider(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
        )

        registry = ToolRegistry()
        registry.register_provider(orch_provider)

        # Check tool appears in registry
        tools = await registry.list_tools()
        tool_names = [t.name for t in tools]
        assert "decompose_task" in tool_names

        # Call the tool
        result = await registry.call_tool(
            "decompose_task",
            {"task": "Build a web app", "agent_id": deps["parent"].id},
        )
        assert result.success
        data = json.loads(result.output)
        assert "plan_id" in data
        assert "subtasks" in data

    @pytest.mark.asyncio
    async def test_st_v2_3_11_orchestrate_tool_e2e(self, deps):
        """ST-V2-3.11: orchestrate tool runs end-to-end."""
        from agent_platform.orchestration.tool_provider import (
            OrchestrationToolProvider,
        )

        mock_llm = deps["llm"]
        call_count = 0

        async def multi_response(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Decomposition response
                return LLMResponse(
                    content=json.dumps(
                        {
                            "subtasks": [
                                {
                                    "description": "Research",
                                    "assigned_to": "spawn_agent",
                                },
                                {
                                    "description": "Write",
                                    "assigned_to": "spawn_agent",
                                },
                            ],
                            "strategy": "sequential",
                        }
                    ),
                    usage={},
                )
            elif call_count <= 3:
                # Subtask execution responses
                return LLMResponse(content=f"Subtask {call_count - 1} done", usage={})
            else:
                # Synthesis response
                return LLMResponse(content="Final synthesized response", usage={})

        mock_llm.complete.side_effect = multi_response

        orch_provider = OrchestrationToolProvider(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
        )

        result = await orch_provider.call_tool(
            "orchestrate",
            {"task": "Write a report on AI", "agent_id": deps["parent"].id},
        )

        assert result.success
        data = json.loads(result.output)
        assert "synthesized_response" in data
        assert len(data["synthesized_response"]) > 0

    @pytest.mark.asyncio
    async def test_st_v2_3_12_orchestration_events(self, deps):
        """ST-V2-3.12: Orchestration emits events."""
        from agent_platform.observation.events import EventFilter
        from agent_platform.orchestration.tool_provider import (
            OrchestrationToolProvider,
        )

        mock_llm = deps["llm"]
        call_count = 0

        async def multi_response(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    content=json.dumps(
                        {
                            "subtasks": [
                                {
                                    "description": "Only task",
                                    "assigned_to": "spawn_agent",
                                },
                            ],
                            "strategy": "sequential",
                        }
                    ),
                    usage={},
                )
            elif call_count == 2:
                return LLMResponse(content="Task done", usage={})
            else:
                return LLMResponse(content="Synthesized", usage={})

        mock_llm.complete.side_effect = multi_response

        orch_provider = OrchestrationToolProvider(
            llm_provider=mock_llm,
            tool_registry=deps["tool_registry"],
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            event_bus=deps["event_bus"],
        )

        await orch_provider.call_tool(
            "orchestrate",
            {"task": "Test events", "agent_id": deps["parent"].id},
        )

        # Query events for this agent
        events = await deps["event_bus"].query(EventFilter(agent_id=deps["parent"].id))

        # Should have events for orchestration
        assert len(events) >= 1
        # Check that orchestration-related events exist
        modules = [e.module for e in events]
        assert any("orchestration" in m for m in modules)
