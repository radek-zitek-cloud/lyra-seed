"""
Smoke tests for V1 Phase 1 — Abstractions & Event System.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-1"),
]


class TestV1Phase1:
    """ST-1.x: Abstractions & Event System smoke tests."""

    def test_st_1_1_llm_provider_protocol(self):
        """ST-1.1: LLM provider protocol is defined."""
        from agent_platform.llm.models import (
            LLMConfig,
            LLMResponse,
            Message,
            MessageRole,
            ToolCall,
        )
        from agent_platform.llm.provider import LLMProvider

        # Protocol has complete method
        assert hasattr(LLMProvider, "complete")

        # Models can be instantiated
        msg = Message(role=MessageRole.HUMAN, content="Hello")
        assert msg.role == MessageRole.HUMAN
        assert msg.content == "Hello"

        tool_call = ToolCall(
            id="tc-1", name="test_tool", arguments={"key": "value"}
        )
        assert tool_call.name == "test_tool"

        response = LLMResponse(
            content="Hi there",
            tool_calls=[tool_call],
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert response.content == "Hi there"
        assert len(response.tool_calls) == 1

        config = LLMConfig(model="test-model")
        assert config.model == "test-model"

    def test_st_1_2_embedding_provider_protocol(self):
        """ST-1.2: Embedding provider protocol is defined."""
        from agent_platform.llm.embeddings import EmbeddingProvider

        assert hasattr(EmbeddingProvider, "embed")
        assert hasattr(EmbeddingProvider, "embed_query")

    def test_st_1_3_repository_protocol(self):
        """ST-1.3: Repository protocol is defined."""
        from agent_platform.db.repository import Repository

        assert hasattr(Repository, "get")
        assert hasattr(Repository, "list")
        assert hasattr(Repository, "create")
        assert hasattr(Repository, "update")
        assert hasattr(Repository, "delete")

    def test_st_1_4_vector_store_protocol(self):
        """ST-1.4: VectorStore protocol is defined."""
        from agent_platform.db.vector_store import VectorResult, VectorStore

        assert hasattr(VectorStore, "store")
        assert hasattr(VectorStore, "search")
        assert hasattr(VectorStore, "delete")

        result = VectorResult(
            id="v-1", score=0.95, metadata={"key": "value"}
        )
        assert result.score == 0.95

    def test_st_1_5_strategy_protocol(self):
        """ST-1.5: Strategy protocol is defined."""
        from agent_platform.core.strategy import Strategy

        assert hasattr(Strategy, "execute")

    def test_st_1_6_event_model_and_types(self):
        """ST-1.6: Event model and types are defined."""
        from agent_platform.observation.events import (
            Event,
            EventFilter,
            EventType,
        )

        # Check key enum values exist
        assert EventType.LLM_REQUEST is not None
        assert EventType.LLM_RESPONSE is not None
        assert EventType.TOOL_CALL is not None
        assert EventType.TOOL_RESULT is not None
        assert EventType.ERROR is not None

        # Event can be instantiated (id/timestamp auto-generated)
        event = Event(
            agent_id="agent-1",
            event_type=EventType.LLM_REQUEST,
            module="llm.openrouter",
            payload={"prompt": "Hello"},
        )
        assert event.id is not None
        assert event.timestamp is not None
        assert event.agent_id == "agent-1"
        assert event.payload == {"prompt": "Hello"}

        # EventFilter with optional fields
        ef = EventFilter(agent_id="agent-1", event_types=[EventType.ERROR])
        assert ef.agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_st_1_7_event_emit_and_subscribe(self):
        """ST-1.7: Events can be emitted and received by subscribers."""
        from agent_platform.observation.events import Event, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        bus = InProcessEventBus()

        # --- Basic emit/receive ---
        sub_all = bus.subscribe()
        event = Event(
            agent_id="agent-1",
            event_type=EventType.LLM_REQUEST,
            module="llm",
            payload={"data": "test"},
        )
        await bus.emit(event)

        received = await asyncio.wait_for(sub_all.__anext__(), timeout=2.0)
        assert received.id == event.id

        # --- Filter by event_type ---
        sub_errors = bus.subscribe(event_types=[EventType.ERROR])
        llm_event = Event(
            agent_id="agent-1",
            event_type=EventType.LLM_REQUEST,
            module="llm",
            payload={},
        )
        error_event = Event(
            agent_id="agent-1",
            event_type=EventType.ERROR,
            module="core",
            payload={"error": "boom"},
        )
        await bus.emit(llm_event)
        await bus.emit(error_event)

        received = await asyncio.wait_for(
            sub_errors.__anext__(), timeout=2.0
        )
        assert received.event_type == EventType.ERROR

        # --- Filter by agent_id ---
        sub_agent2 = bus.subscribe(agent_id="agent-2")
        event_a1 = Event(
            agent_id="agent-1",
            event_type=EventType.LLM_REQUEST,
            module="llm",
            payload={},
        )
        event_a2 = Event(
            agent_id="agent-2",
            event_type=EventType.LLM_RESPONSE,
            module="llm",
            payload={},
        )
        await bus.emit(event_a1)
        await bus.emit(event_a2)

        received = await asyncio.wait_for(
            sub_agent2.__anext__(), timeout=2.0
        )
        assert received.agent_id == "agent-2"

        # --- Multiple subscribers ---
        sub_x = bus.subscribe()
        sub_y = bus.subscribe()
        shared_event = Event(
            agent_id="agent-1",
            event_type=EventType.TOOL_CALL,
            module="tools",
            payload={},
        )
        await bus.emit(shared_event)

        rx = await asyncio.wait_for(sub_x.__anext__(), timeout=2.0)
        ry = await asyncio.wait_for(sub_y.__anext__(), timeout=2.0)
        assert rx.id == shared_event.id
        assert ry.id == shared_event.id

    @pytest.mark.asyncio
    async def test_st_1_8_event_sqlite_persistence(self, tmp_path):
        """ST-1.8: Events persist to SQLite and can be queried."""
        from agent_platform.observation.events import (
            Event,
            EventFilter,
            EventType,
        )
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        db_path = str(tmp_path / "test_events.db")
        bus = InProcessEventBus(db_path=db_path)
        await bus.initialize()

        # Emit events
        e1 = Event(
            agent_id="agent-1",
            event_type=EventType.LLM_REQUEST,
            module="llm",
            payload={"prompt": "hello"},
        )
        e2 = Event(
            agent_id="agent-1",
            event_type=EventType.ERROR,
            module="core",
            payload={"error": "oops"},
        )
        e3 = Event(
            agent_id="agent-2",
            event_type=EventType.TOOL_CALL,
            module="tools",
            payload={"tool": "search"},
        )
        await bus.emit(e1)
        await bus.emit(e2)
        await bus.emit(e3)

        # Query by agent_id
        results = await bus.query(EventFilter(agent_id="agent-1"))
        assert len(results) == 2
        assert all(r.agent_id == "agent-1" for r in results)

        # Query by event_type
        results = await bus.query(
            EventFilter(event_types=[EventType.ERROR])
        )
        assert len(results) == 1
        assert results[0].event_type == EventType.ERROR

        # Query by time range
        now = datetime.now(UTC)
        results = await bus.query(
            EventFilter(
                time_from=now - timedelta(minutes=5),
                time_to=now + timedelta(minutes=5),
            )
        )
        assert len(results) == 3

        # Payload roundtrip
        results = await bus.query(EventFilter(agent_id="agent-1"))
        llm_events = [
            r for r in results if r.event_type == EventType.LLM_REQUEST
        ]
        assert len(llm_events) == 1
        assert llm_events[0].payload == {"prompt": "hello"}

        await bus.close()

    @pytest.mark.asyncio
    async def test_st_1_9_event_bus_in_app(self):
        """ST-1.9: EventBus is accessible from the FastAPI app."""
        from agent_platform.api.main import create_app
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        app = create_app()
        assert hasattr(app.state, "event_bus")
        assert isinstance(app.state.event_bus, InProcessEventBus)
