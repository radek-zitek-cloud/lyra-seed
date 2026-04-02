"""
Smoke tests for V2 Phase 1 — Sub-Agent Spawning & Lifecycle.

Tests: spawn_agent tool, wait_for_agent, get_agent_result, list_child_agents,
lifecycle events, parent-child queries, config inheritance.
All LLM calls are mocked.
"""

import json
from unittest.mock import AsyncMock

import pytest

from agent_platform.core.models import Agent, AgentConfig
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.llm.models import LLMResponse
from agent_platform.observation.events import EventFilter, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v2-phase-1"),
]


@pytest.fixture
async def deps(tmp_path):
    """Set up shared test dependencies."""
    agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
    await agent_repo.initialize()
    conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
    await conv_repo.initialize()
    event_bus = InProcessEventBus(db_path=str(tmp_path / "events.db"))
    await event_bus.initialize()

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="Child response.", usage={"prompt_tokens": 10, "completion_tokens": 5}
    )

    yield {
        "agent_repo": agent_repo,
        "conv_repo": conv_repo,
        "event_bus": event_bus,
        "llm": mock_llm,
        "tmp_path": tmp_path,
    }

    await agent_repo.close()
    await conv_repo.close()
    await event_bus.close()


class TestV2Phase1:
    """ST-V2-1.x: Sub-Agent Spawning & Lifecycle smoke tests."""

    @pytest.mark.asyncio
    async def test_st_v2_1_1_spawn_agent_tool_schema(self, deps):
        """ST-V2-1.1: AgentSpawnerProvider lists spawn_agent tool."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )
        tools = await provider.list_tools()
        names = [t.name for t in tools]

        assert "spawn_agent" in names
        spawn_tool = next(t for t in tools if t.name == "spawn_agent")
        required = spawn_tool.input_schema.get("required", [])
        assert "name" in required
        assert "task" in required
        props = spawn_tool.input_schema.get("properties", {})
        assert "system_prompt" in props
        assert "model" in props

    @pytest.mark.asyncio
    async def test_st_v2_1_2_spawn_agent_creates_child(self, deps):
        """ST-V2-1.2: spawn_agent creates a child agent linked to parent."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        # Create parent agent
        parent = Agent(name="parent", config=AgentConfig(model="test/model"))
        await deps["agent_repo"].create(parent)

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )

        result = await provider.call_tool(
            "spawn_agent",
            {"name": "child-1", "task": "Do something", "agent_id": parent.id},
        )

        assert result.success is True
        output = json.loads(result.output)
        child_id = output["child_agent_id"]

        # Verify child exists with correct parent
        child = await deps["agent_repo"].get(child_id)
        assert child is not None
        assert child.parent_agent_id == parent.id
        assert child.name == "child-1"

    @pytest.mark.asyncio
    async def test_st_v2_1_3_spawn_agent_emits_agent_spawn(self, deps):
        """ST-V2-1.3: AGENT_SPAWN event emitted when child is spawned."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        parent = Agent(name="parent", config=AgentConfig(model="test/model"))
        await deps["agent_repo"].create(parent)

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )

        await provider.call_tool(
            "spawn_agent",
            {"name": "child-ev", "task": "Do work", "agent_id": parent.id},
        )

        events = await deps["event_bus"].query(
            EventFilter(
                agent_id=parent.id,
                event_types=[EventType.AGENT_SPAWN],
            )
        )
        assert len(events) >= 1
        assert "child_agent_id" in events[0].payload
        assert events[0].payload["child_name"] == "child-ev"

    @pytest.mark.asyncio
    async def test_st_v2_1_4_spawn_agent_emits_agent_complete(self, deps):
        """ST-V2-1.4: AGENT_COMPLETE event emitted when child finishes."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        parent = Agent(name="parent", config=AgentConfig(model="test/model"))
        await deps["agent_repo"].create(parent)

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )

        result = await provider.call_tool(
            "spawn_agent",
            {"name": "child-comp", "task": "Do work", "agent_id": parent.id},
        )
        output = json.loads(result.output)
        child_id = output["child_agent_id"]

        events = await deps["event_bus"].query(
            EventFilter(
                agent_id=child_id,
                event_types=[EventType.AGENT_COMPLETE],
            )
        )
        assert len(events) >= 1
        assert events[0].payload.get("parent_agent_id") == parent.id

    @pytest.mark.asyncio
    async def test_st_v2_1_5_spawn_agent_child_failure_safe(self, deps):
        """ST-V2-1.5: Child agent failure doesn't crash the parent."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        parent = Agent(name="parent", config=AgentConfig(model="test/model"))
        await deps["agent_repo"].create(parent)

        # LLM that raises error for child
        failing_llm = AsyncMock()
        failing_llm.complete.side_effect = RuntimeError("LLM failed")

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=failing_llm,
            event_bus=deps["event_bus"],
        )

        result = await provider.call_tool(
            "spawn_agent",
            {"name": "child-fail", "task": "Do work", "agent_id": parent.id},
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_st_v2_1_6_get_agent_result(self, deps):
        """ST-V2-1.6: get_agent_result returns child's response."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        parent = Agent(name="parent", config=AgentConfig(model="test/model"))
        await deps["agent_repo"].create(parent)

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )

        spawn_result = await provider.call_tool(
            "spawn_agent",
            {"name": "child-res", "task": "Work", "agent_id": parent.id},
        )
        child_id = json.loads(spawn_result.output)["child_agent_id"]

        result = await provider.call_tool(
            "get_agent_result",
            {"child_agent_id": child_id, "agent_id": parent.id},
        )

        assert result.success is True
        output = json.loads(result.output)
        assert output["status"] in ("idle", "completed")
        assert output["content"] is not None

    @pytest.mark.asyncio
    async def test_st_v2_1_7_list_child_agents(self, deps):
        """ST-V2-1.7: list_child_agents returns spawned children."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        parent = Agent(name="parent", config=AgentConfig(model="test/model"))
        await deps["agent_repo"].create(parent)

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )

        # Spawn two children
        await provider.call_tool(
            "spawn_agent",
            {"name": "child-a", "task": "Work A", "agent_id": parent.id},
        )
        await provider.call_tool(
            "spawn_agent",
            {"name": "child-b", "task": "Work B", "agent_id": parent.id},
        )

        result = await provider.call_tool("list_child_agents", {"agent_id": parent.id})

        assert result.success is True
        children = json.loads(result.output)
        assert len(children) == 2
        names = {c["name"] for c in children}
        assert names == {"child-a", "child-b"}

    @pytest.mark.asyncio
    async def test_st_v2_1_8_list_children_repo(self, deps):
        """ST-V2-1.8: SqliteAgentRepo.list_children() queries correctly."""
        repo = deps["agent_repo"]

        parent = Agent(name="parent")
        await repo.create(parent)

        child1 = Agent(name="child-1", parent_agent_id=parent.id)
        child2 = Agent(name="child-2", parent_agent_id=parent.id)
        unrelated = Agent(name="unrelated")
        await repo.create(child1)
        await repo.create(child2)
        await repo.create(unrelated)

        children = await repo.list_children(parent.id)
        assert len(children) == 2
        ids = {c.id for c in children}
        assert child1.id in ids
        assert child2.id in ids
        assert unrelated.id not in ids

    @pytest.mark.asyncio
    async def test_st_v2_1_9_children_api_endpoint(self, deps):
        """ST-V2-1.9: GET /agents/{id}/children returns child agents."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        settings = Settings(openrouter_api_key="sk-test")  # type: ignore[arg-type]
        app = create_app(settings, db_dir=str(deps["tmp_path"] / "api"))

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Create parent via API
                resp = await client.post("/agents", json={"name": "api-parent"})
                assert resp.status_code == 201
                parent_id = resp.json()["id"]

                # Create child with parent_agent_id directly in DB
                from agent_platform.api._deps import get_agent_repo

                repo = get_agent_repo()
                child = Agent(
                    name="api-child",
                    parent_agent_id=parent_id,
                )
                await repo.create(child)

                resp = await client.get(f"/agents/{parent_id}/children")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) >= 1
                assert any(c["name"] == "api-child" for c in data)

    @pytest.mark.asyncio
    async def test_st_v2_1_10_wait_for_agent(self, deps):
        """ST-V2-1.10: wait_for_agent returns child's result."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        parent = Agent(name="parent", config=AgentConfig(model="test/model"))
        await deps["agent_repo"].create(parent)

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )

        spawn_result = await provider.call_tool(
            "spawn_agent",
            {"name": "child-wait", "task": "Work", "agent_id": parent.id},
        )
        child_id = json.loads(spawn_result.output)["child_agent_id"]

        result = await provider.call_tool(
            "wait_for_agent",
            {"child_agent_id": child_id, "agent_id": parent.id},
        )

        assert result.success is True
        output = json.loads(result.output)
        assert output["content"] is not None

    @pytest.mark.asyncio
    async def test_st_v2_1_11_agent_id_injection(self, deps):
        """ST-V2-1.11: Runtime injects agent_id into spawner tool arguments."""
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider
        from agent_platform.tools.registry import ToolRegistry

        parent = Agent(
            name="parent",
            config=AgentConfig(model="test/model", max_iterations=2),
        )
        await deps["agent_repo"].create(parent)

        # LLM returns spawn_agent tool call WITHOUT agent_id
        from agent_platform.llm.models import ToolCall

        parent_llm = AsyncMock()
        parent_llm.complete.side_effect = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="spawn_agent",
                        arguments={"name": "sub", "task": "do it"},
                    )
                ],
                usage={},
            ),
            LLMResponse(content="Done.", usage={}),
        ]

        child_llm = AsyncMock()
        child_llm.complete.return_value = LLMResponse(content="Child done.", usage={})

        spawner = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=child_llm,
            event_bus=deps["event_bus"],
        )

        registry = ToolRegistry()
        registry.register_provider(spawner)

        runtime = AgentRuntime(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=parent_llm,
            event_bus=deps["event_bus"],
            tool_registry=registry,
        )

        response = await runtime.run(parent.id, "Spawn a sub-agent")
        assert response.content == "Done."

        # Verify child was created with correct parent
        children = await deps["agent_repo"].list_children(parent.id)
        assert len(children) == 1
        assert children[0].parent_agent_id == parent.id

    @pytest.mark.asyncio
    async def test_st_v2_1_12_child_inherits_parent_config(self, deps):
        """ST-V2-1.12: Child inherits model and temperature from parent."""
        from agent_platform.tools.agent_spawner import AgentSpawnerProvider

        parent = Agent(
            name="parent",
            config=AgentConfig(model="custom/parent-model", temperature=0.3),
        )
        await deps["agent_repo"].create(parent)

        provider = AgentSpawnerProvider(
            agent_repo=deps["agent_repo"],
            conversation_repo=deps["conv_repo"],
            llm_provider=deps["llm"],
            event_bus=deps["event_bus"],
        )

        result = await provider.call_tool(
            "spawn_agent",
            {"name": "child-inherit", "task": "Work", "agent_id": parent.id},
        )
        child_id = json.loads(result.output)["child_agent_id"]

        child = await deps["agent_repo"].get(child_id)
        assert child.config.model == "custom/parent-model"
        assert child.config.temperature == 0.3
