"""
Smoke tests for V1 Phase 5 — Observation UI.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
All LLM calls are mocked — no real API calls.
"""

import asyncio

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

        # Add a macro via the macro routes
        await client.post(
            "/macros",
            json={
                "name": "test_macro",
                "description": "A test macro",
                "template": "Do {{thing}}",
                "parameters": {
                    "type": "object",
                    "properties": {"thing": {"type": "string"}},
                },
            },
        )

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
        _, app = app_client

        from unittest.mock import AsyncMock as _AsyncMock

        from fastapi import WebSocketDisconnect

        from agent_platform.api.ws_routes import agent_event_stream
        from agent_platform.observation.events import Event, EventType

        event_bus = app.state.event_bus
        agent_id = "ws-test-agent"

        # Mock WebSocket — capture sent data, disconnect after first event
        mock_ws = _AsyncMock()
        received: list[dict] = []

        async def capture_and_disconnect(data):
            received.append(data)
            raise WebSocketDisconnect()

        mock_ws.send_json = capture_and_disconnect

        event = Event(
            agent_id=agent_id,
            event_type=EventType.LLM_REQUEST,
            module="llm.test",
            payload={"model": "test"},
        )

        async def emit_after_delay():
            await asyncio.sleep(0.05)
            await event_bus.emit(event)

        await asyncio.gather(
            agent_event_stream(mock_ws, agent_id),
            emit_after_delay(),
        )

        mock_ws.accept.assert_called_once()
        assert len(received) == 1
        assert received[0]["agent_id"] == agent_id
        assert received[0]["event_type"] == "llm_request"

    @pytest.mark.asyncio
    async def test_st_5_7_ws_global_event_stream(self, app_client):
        """ST-5.7: WebSocket global event stream."""
        _, app = app_client

        from unittest.mock import AsyncMock as _AsyncMock2

        from fastapi import WebSocketDisconnect

        from agent_platform.api.ws_routes import global_event_stream
        from agent_platform.observation.events import Event, EventType

        event_bus = app.state.event_bus

        mock_ws = _AsyncMock2()
        received: list[dict] = []
        call_count = 0

        async def capture_send(data):
            nonlocal call_count
            received.append(data)
            call_count += 1
            if call_count >= 2:
                raise WebSocketDisconnect()

        mock_ws.send_json = capture_send

        async def emit_events():
            await asyncio.sleep(0.05)
            await event_bus.emit(
                Event(
                    agent_id="agent-x",
                    event_type=EventType.LLM_REQUEST,
                    module="llm.test",
                    payload={},
                )
            )
            await event_bus.emit(
                Event(
                    agent_id="agent-y",
                    event_type=EventType.TOOL_CALL,
                    module="tools.test",
                    payload={},
                )
            )

        await asyncio.gather(
            global_event_stream(mock_ws),
            emit_events(),
        )

        mock_ws.accept.assert_called_once()
        assert len(received) == 2
        agent_ids = {r["agent_id"] for r in received}
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
