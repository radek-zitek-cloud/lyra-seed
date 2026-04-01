"""
Smoke tests for V1 Phase 2 — Agent Runtime.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
All LLM calls are mocked — no real API calls.
"""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-2"),
]


class TestV1Phase2:
    """ST-2.x: Agent Runtime smoke tests."""

    def test_st_2_1_agent_data_model(self):
        """ST-2.1: Agent data model."""
        from agent_platform.core.models import (
            Agent,
            AgentConfig,
            AgentResponse,
            AgentStatus,
            Conversation,
            HITLPolicy,
        )
        from agent_platform.llm.models import Message, MessageRole

        # AgentStatus enum
        assert AgentStatus.IDLE is not None
        assert AgentStatus.RUNNING is not None
        assert AgentStatus.WAITING_HITL is not None
        assert AgentStatus.COMPLETED is not None
        assert AgentStatus.FAILED is not None

        # HITLPolicy enum
        assert HITLPolicy.ALWAYS_ASK is not None
        assert HITLPolicy.DANGEROUS_ONLY is not None
        assert HITLPolicy.NEVER is not None

        # AgentConfig
        config = AgentConfig(
            model="test-model",
            temperature=0.5,
            max_iterations=10,
            system_prompt="You are helpful.",
        )
        assert config.max_iterations == 10

        # Agent auto-generates id and timestamps
        agent = Agent(name="test-agent", config=config)
        assert agent.id is not None
        assert agent.created_at is not None
        assert agent.updated_at is not None
        assert agent.status == AgentStatus.IDLE
        assert agent.parent_agent_id is None

        # Conversation
        conv = Conversation(
            agent_id=agent.id,
            messages=[
                Message(role=MessageRole.HUMAN, content="Hello"),
            ],
        )
        assert conv.id is not None
        assert len(conv.messages) == 1

        # AgentResponse
        resp = AgentResponse(agent_id=agent.id, content="Hi there")
        assert resp.content == "Hi there"

    @pytest.mark.asyncio
    async def test_st_2_2_agent_sqlite_repo(self, tmp_path):
        """ST-2.2: Agent SQLite repository CRUD."""
        from agent_platform.core.models import Agent, AgentConfig, AgentStatus
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo

        db_path = str(tmp_path / "test_agents.db")
        repo = SqliteAgentRepo(db_path)
        await repo.initialize()

        config = AgentConfig(model="test-model")
        agent = Agent(name="test-agent", config=config)

        # Create
        created = await repo.create(agent)
        assert created.id == agent.id
        assert created.name == "test-agent"

        # Get
        fetched = await repo.get(agent.id)
        assert fetched is not None
        assert fetched.name == "test-agent"
        assert fetched.config.model == "test-model"

        # Update
        agent.status = AgentStatus.RUNNING
        updated = await repo.update(agent.id, agent)
        assert updated.status == AgentStatus.RUNNING

        # List
        agent2 = Agent(name="agent-2", config=config)
        await repo.create(agent2)
        all_agents = await repo.list()
        assert len(all_agents) == 2

        # Delete
        deleted = await repo.delete(agent.id)
        assert deleted is True
        all_agents = await repo.list()
        assert len(all_agents) == 1

        await repo.close()

    @pytest.mark.asyncio
    async def test_st_2_3_conversation_sqlite_repo(self, tmp_path):
        """ST-2.3: Conversation SQLite repository."""
        from agent_platform.core.models import Conversation
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import Message, MessageRole, ToolCall

        db_path = str(tmp_path / "test_convos.db")
        repo = SqliteConversationRepo(db_path)
        await repo.initialize()

        # Create conversation with messages
        conv = Conversation(
            agent_id="agent-1",
            messages=[
                Message(role=MessageRole.SYSTEM, content="You are helpful."),
                Message(role=MessageRole.HUMAN, content="Hello"),
                Message(
                    role=MessageRole.ASSISTANT,
                    content="Hi!",
                    tool_calls=[
                        ToolCall(
                            id="tc-1",
                            name="search",
                            arguments={"q": "test"},
                        )
                    ],
                ),
            ],
        )
        await repo.create(conv)

        # Retrieve and verify roundtrip
        fetched = await repo.get(conv.id)
        assert fetched is not None
        assert len(fetched.messages) == 3
        assert fetched.messages[0].role == MessageRole.SYSTEM
        assert fetched.messages[1].content == "Hello"
        assert fetched.messages[2].tool_calls is not None
        assert fetched.messages[2].tool_calls[0].name == "search"

        # Update with new message
        conv.messages.append(Message(role=MessageRole.HUMAN, content="Thanks!"))
        await repo.update(conv.id, conv)
        fetched = await repo.get(conv.id)
        assert fetched is not None
        assert len(fetched.messages) == 4

        await repo.close()

    @pytest.mark.asyncio
    async def test_st_2_4_openrouter_provider(self):
        """ST-2.4: OpenRouter provider request/response mapping."""
        from agent_platform.llm.models import (
            LLMConfig,
            Message,
            MessageRole,
        )
        from agent_platform.llm.openrouter import OpenRouterProvider
        from agent_platform.observation.events import EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        # Mock HTTP response from OpenRouter
        mock_response_data = {
            "id": "gen-123",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
        }

        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=mock_response_data)
        )
        client = httpx.AsyncClient(transport=transport)
        event_bus = InProcessEventBus()

        provider = OpenRouterProvider(
            api_key="sk-test-key",
            http_client=client,
            event_bus=event_bus,
        )

        # Subscribe to capture events
        events_received: list = []
        sub = event_bus.subscribe()

        messages = [
            Message(role=MessageRole.HUMAN, content="Hi"),
        ]
        config = LLMConfig(model="test/model")

        response = await provider.complete(messages, config=config)

        assert response.content == "Hello! How can I help?"
        assert response.usage["prompt_tokens"] == 10

        # Collect emitted events
        for _ in range(2):  # LLM_REQUEST + LLM_RESPONSE
            evt = await asyncio.wait_for(sub.__anext__(), timeout=2.0)
            events_received.append(evt)

        event_types = [e.event_type for e in events_received]
        assert EventType.LLM_REQUEST in event_types
        assert EventType.LLM_RESPONSE in event_types

    @pytest.mark.asyncio
    async def test_st_2_5_runtime_text_response(self, tmp_path):
        """ST-2.5: Agent runtime core loop (text response)."""
        from agent_platform.core.models import (
            Agent,
            AgentConfig,
            AgentStatus,
        )
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        db_path = str(tmp_path / "test_runtime.db")
        event_bus = InProcessEventBus(db_path=db_path)
        await event_bus.initialize()

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        # Create agent
        config = AgentConfig(model="test/model", system_prompt="Be helpful.")
        agent = Agent(name="test-agent", config=config)
        await agent_repo.create(agent)

        # Mock LLM provider
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="I can help with that!",
            usage={"prompt_tokens": 15, "completion_tokens": 6},
        )

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
        )

        response = await runtime.run(agent.id, "Help me with something")

        assert response.content == "I can help with that!"
        assert response.agent_id == agent.id

        # Agent should be back to IDLE
        updated_agent = await agent_repo.get(agent.id)
        assert updated_agent is not None
        assert updated_agent.status == AgentStatus.IDLE

        # Events should have been emitted
        events = await event_bus.query(EventFilter(agent_id=agent.id))
        event_types = [e.event_type for e in events]
        assert EventType.LLM_REQUEST in event_types
        assert EventType.LLM_RESPONSE in event_types

        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_2_6_runtime_tool_call_loop(self, tmp_path):
        """ST-2.6: Agent runtime tool call loop."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse, ToolCall
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        db_path = str(tmp_path / "events.db")
        event_bus = InProcessEventBus(db_path=db_path)
        await event_bus.initialize()

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        config = AgentConfig(model="test/model")
        agent = Agent(name="tool-agent", config=config)
        await agent_repo.create(agent)

        # First call returns tool call, second returns text
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="tc-1",
                        name="search",
                        arguments={"query": "test"},
                    )
                ],
                usage={"prompt_tokens": 10, "completion_tokens": 5},
            ),
            LLMResponse(
                content="Based on the search results, here is your answer.",
                usage={"prompt_tokens": 20, "completion_tokens": 12},
            ),
        ]

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
        )

        response = await runtime.run(agent.id, "Search for something")

        assert response.content is not None
        assert "answer" in response.content.lower()
        assert mock_llm.complete.call_count == 2

        # Check events
        events = await event_bus.query(EventFilter(agent_id=agent.id))
        event_types = [e.event_type for e in events]
        assert EventType.TOOL_CALL in event_types
        assert EventType.TOOL_RESULT in event_types

        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_2_7_max_iterations_guard(self, tmp_path):
        """ST-2.7: Max iterations guard."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse, ToolCall
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        db_path = str(tmp_path / "events.db")
        event_bus = InProcessEventBus(db_path=db_path)
        await event_bus.initialize()

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        # max_iterations=2 — LLM always returns tool calls
        config = AgentConfig(model="test/model", max_iterations=2)
        agent = Agent(name="looping-agent", config=config)
        await agent_repo.create(agent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content=None,
            tool_calls=[ToolCall(id="tc-x", name="loop_tool", arguments={})],
            usage={"prompt_tokens": 5, "completion_tokens": 3},
        )

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
        )

        response = await runtime.run(agent.id, "Do something")

        # Should have stopped and indicated the limit
        assert response.content is not None
        assert mock_llm.complete.call_count <= 3  # at most max_iterations + 1

        # Check for ERROR event
        events = await event_bus.query(EventFilter(agent_id=agent.id))
        event_types = [e.event_type for e in events]
        assert EventType.ERROR in event_types

        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_2_8_hitl_permission_gate(self, tmp_path):
        """ST-2.8: HITL permission gate."""
        from agent_platform.core.models import (
            Agent,
            AgentConfig,
            AgentStatus,
            HITLPolicy,
        )
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse, ToolCall
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        event_bus = InProcessEventBus()
        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        config = AgentConfig(
            model="test/model",
            hitl_policy=HITLPolicy.ALWAYS_ASK,
        )
        agent = Agent(name="hitl-agent", config=config)
        await agent_repo.create(agent)

        # LLM returns tool call, then text after approval
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="tc-1", name="dangerous_tool", arguments={})],
                usage={},
            ),
            LLMResponse(
                content="Done after approval.",
                usage={},
            ),
        ]

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
        )

        # Run the agent in background — it will pause at HITL gate
        async def approve_after_delay():
            """Simulate human approving after a short delay."""
            await asyncio.sleep(0.2)
            # Check agent is waiting
            a = await agent_repo.get(agent.id)
            assert a is not None
            assert a.status == AgentStatus.WAITING_HITL
            # Send approval
            await runtime.hitl_respond(agent.id, approved=True, message="Go ahead")

        response, _ = await asyncio.gather(
            runtime.run(agent.id, "Do something dangerous"),
            approve_after_delay(),
        )

        assert response.content == "Done after approval."

        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_2_9_api_endpoints(self, tmp_path):
        """ST-2.9: API endpoints."""
        import httpx as httpx_mod

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        settings = Settings(
            openrouter_api_key="sk-test",  # type: ignore[arg-type]
            db_path=str(tmp_path / "api_test.db"),
        )
        app = create_app(settings, db_dir=str(tmp_path))

        # Manually run lifespan
        async with app.router.lifespan_context(app):
            transport = httpx_mod.ASGITransport(app=app)
            async with httpx_mod.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # POST /agents — create agent
                resp = await client.post(
                    "/agents",
                    json={
                        "name": "api-test-agent",
                        "config": {"model": "test/model"},
                    },
                )
                assert resp.status_code == 201
                agent_data = resp.json()
                assert agent_data["name"] == "api-test-agent"
                agent_id = agent_data["id"]

                # GET /agents/{id}
                resp = await client.get(f"/agents/{agent_id}")
                assert resp.status_code == 200
                assert resp.json()["id"] == agent_id

                # POST /agents/{id}/hitl-respond (no pending gate)
                resp = await client.post(
                    f"/agents/{agent_id}/hitl-respond",
                    json={"approved": True},
                )
                assert resp.status_code in (404, 409)
