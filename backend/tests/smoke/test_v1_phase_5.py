"""
Smoke tests for V1 Phase 5 — Observation UI.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
All LLM calls are mocked — no real API calls.
"""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-5"),
]


@pytest.fixture
async def app_client(tmp_path):
    """Create a test app with initialized repos and return an async httpx client."""
    from agent_platform.api.main import create_app
    from agent_platform.core.config import Settings

    settings = Settings(
        openrouter_api_key="sk-test",  # type: ignore[arg-type]
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(settings, db_dir=str(tmp_path))

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client, app


class TestV1Phase5:
    """ST-5.x: Observation UI smoke tests."""

    @pytest.mark.asyncio
    async def test_st_5_1_list_agents(self, app_client):
        """ST-5.1: List agents endpoint."""
        client, app = app_client

        # Create two agents
        resp1 = await client.post(
            "/agents", json={"name": "agent-a", "config": {"model": "test/model"}}
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/agents", json={"name": "agent-b", "config": {"model": "test/model"}}
        )
        assert resp2.status_code == 201

        # List agents
        resp = await client.get("/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert isinstance(agents, list)
        assert len(agents) == 2
        names = {a["name"] for a in agents}
        assert names == {"agent-a", "agent-b"}
        for a in agents:
            assert "id" in a
            assert "name" in a
            assert "status" in a

    @pytest.mark.asyncio
    async def test_st_5_2_agent_events(self, app_client, tmp_path):
        """ST-5.2: Agent events endpoint."""
        client, app = app_client

        # Create agent
        resp = await client.post(
            "/agents", json={"name": "event-agent", "config": {"model": "test/model"}}
        )
        agent_id = resp.json()["id"]

        # Emit events directly via the event bus
        from agent_platform.observation.events import Event, EventType

        event_bus = app.state.event_bus
        await event_bus.emit(
            Event(
                agent_id=agent_id,
                event_type=EventType.LLM_REQUEST,
                module="llm.test",
                payload={"model": "test"},
            )
        )
        await event_bus.emit(
            Event(
                agent_id=agent_id,
                event_type=EventType.LLM_RESPONSE,
                module="llm.test",
                payload={"content": "hello"},
            )
        )
        await event_bus.emit(
            Event(
                agent_id=agent_id,
                event_type=EventType.TOOL_CALL,
                module="tools.test",
                payload={"tool": "search"},
            )
        )

        # Query all events for agent
        resp = await client.get(f"/agents/{agent_id}/events")
        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)
        assert len(events) == 3
        for e in events:
            assert e["agent_id"] == agent_id

        # Filter by event_type
        resp = await client.get(
            f"/agents/{agent_id}/events", params={"event_type": "tool_call"}
        )
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "tool_call"

    @pytest.mark.asyncio
    async def test_st_5_3_agent_conversations(self, app_client):
        """ST-5.3: Agent conversations endpoint."""
        client, app = app_client

        # Create agent
        resp = await client.post(
            "/agents",
            json={"name": "conv-agent", "config": {"model": "test/model"}},
        )
        agent_id = resp.json()["id"]

        # Create a conversation with messages directly
        from agent_platform.core.models import Conversation
        from agent_platform.llm.models import Message, MessageRole

        conv_repo = app.state.conversation_repo
        conv = Conversation(
            agent_id=agent_id,
            messages=[
                Message(role=MessageRole.SYSTEM, content="You are helpful."),
                Message(role=MessageRole.HUMAN, content="Hello"),
                Message(role=MessageRole.ASSISTANT, content="Hi there!"),
            ],
        )
        await conv_repo.create(conv)

        # Query conversations
        resp = await client.get(f"/agents/{agent_id}/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        conversation = data[0]
        assert "messages" in conversation
        messages = conversation["messages"]
        assert len(messages) == 3
        roles = [m["role"] for m in messages]
        assert "human" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_st_5_4_tools_list(self, app_client):
        """ST-5.4: Tools list endpoint."""
        client, app = app_client

        # Register a macro tool
        from agent_platform.tools.models import Tool, ToolType

        tool_registry = app.state.tool_registry

        # Add a macro via the macro routes
        resp = await client.post(
            "/macros",
            json={
                "name": "test_macro",
                "description": "A test macro",
                "template": "Do {{thing}}",
                "parameters": {"type": "object", "properties": {"thing": {"type": "string"}}},
            },
        )
        # May or may not succeed depending on macro setup, but tools endpoint should work

        resp = await client.get("/tools")
        assert resp.status_code == 200
        tools = resp.json()
        assert isinstance(tools, list)
        # At minimum, the endpoint returns a list (may be empty if no macros loaded)
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "tool_type" in tool

    @pytest.mark.asyncio
    async def test_st_5_5_tool_calls_history(self, app_client):
        """ST-5.5: Tool calls history endpoint."""
        client, app = app_client

        # Emit tool call events directly
        from agent_platform.observation.events import Event, EventType

        event_bus = app.state.event_bus
        await event_bus.emit(
            Event(
                agent_id="agent-1",
                event_type=EventType.TOOL_CALL,
                module="tools.test",
                payload={"tool_name": "search", "arguments": {"q": "test"}},
            )
        )
        await event_bus.emit(
            Event(
                agent_id="agent-1",
                event_type=EventType.TOOL_RESULT,
                module="tools.test",
                payload={"tool_name": "search", "success": True},
            )
        )
        await event_bus.emit(
            Event(
                agent_id="agent-2",
                event_type=EventType.TOOL_CALL,
                module="tools.test",
                payload={"tool_name": "other_tool", "arguments": {}},
            )
        )

        # Query tool calls for "search"
        resp = await client.get("/tools/search/calls")
        assert resp.status_code == 200
        calls = resp.json()
        assert isinstance(calls, list)
        # Should have TOOL_CALL and TOOL_RESULT for "search"
        assert len(calls) >= 1
        for call in calls:
            assert call["payload"]["tool_name"] == "search"

    @pytest.mark.asyncio
    async def test_st_5_6_ws_agent_event_stream(self, app_client):
        """ST-5.6: WebSocket agent event stream."""
        client, app = app_client

        # Create agent
        resp = await client.post(
            "/agents",
            json={"name": "ws-agent", "config": {"model": "test/model"}},
        )
        agent_id = resp.json()["id"]

        from agent_platform.observation.events import Event, EventType
        from starlette.testclient import TestClient

        sync_client = TestClient(app)

        with sync_client.websocket_connect(
            f"/agents/{agent_id}/events/stream"
        ) as ws:
            # Emit an event in a background task
            event = Event(
                agent_id=agent_id,
                event_type=EventType.LLM_REQUEST,
                module="llm.test",
                payload={"model": "test"},
            )

            # We need to emit from within the same event loop
            # Use a thread to emit since TestClient runs its own loop
            import json
            import threading

            def emit_event():
                import asyncio as _asyncio

                loop = _asyncio.new_event_loop()
                loop.run_until_complete(app.state.event_bus.emit(event))
                loop.close()

            threading.Thread(target=emit_event, daemon=True).start()

            # Receive the event
            data = ws.receive_json(mode="text")
            assert data["agent_id"] == agent_id
            assert data["event_type"] == "llm_request"

    @pytest.mark.asyncio
    async def test_st_5_7_ws_global_event_stream(self, app_client):
        """ST-5.7: WebSocket global event stream."""
        client, app = app_client

        from agent_platform.observation.events import Event, EventType
        from starlette.testclient import TestClient

        sync_client = TestClient(app)

        with sync_client.websocket_connect("/events/stream") as ws:
            import threading

            def emit_events():
                import asyncio as _asyncio

                async def _emit():
                    await app.state.event_bus.emit(
                        Event(
                            agent_id="agent-x",
                            event_type=EventType.LLM_REQUEST,
                            module="llm.test",
                            payload={},
                        )
                    )
                    await app.state.event_bus.emit(
                        Event(
                            agent_id="agent-y",
                            event_type=EventType.TOOL_CALL,
                            module="tools.test",
                            payload={},
                        )
                    )

                loop = _asyncio.new_event_loop()
                loop.run_until_complete(_emit())
                loop.close()

            threading.Thread(target=emit_events, daemon=True).start()

            # Receive events from different agents
            data1 = ws.receive_json(mode="text")
            data2 = ws.receive_json(mode="text")
            agent_ids = {data1["agent_id"], data2["agent_id"]}
            assert "agent-x" in agent_ids
            assert "agent-y" in agent_ids

    @pytest.mark.asyncio
    async def test_st_5_8_cors_headers(self, app_client):
        """ST-5.8: CORS headers present."""
        client, app = app_client

        resp = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS preflight should return appropriate headers
        assert "access-control-allow-origin" in resp.headers
        assert "access-control-allow-methods" in resp.headers
