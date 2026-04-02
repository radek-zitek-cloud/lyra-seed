"""
Smoke tests for V1 Phase 6 — Pre-V2 Hardening.

Tests: retry, HITL timeout, memory GC, context compression, cost tracking.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-6"),
]


class TestV1Phase6:
    """ST-6.x: Pre-V2 Hardening smoke tests."""

    @pytest.mark.asyncio
    async def test_st_6_1_retry_on_429(self):
        """ST-6.1: Retry on 429."""
        from agent_platform.llm.retry import async_retry

        call_count = 0

        async def mock_request():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(429, text="Rate limited")
            return httpx.Response(200, json={"ok": True})

        resp = await async_retry(mock_request, max_retries=3, base_delay=0.01)
        assert resp.status_code == 200
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_st_6_2_no_retry_on_500(self):
        """ST-6.2: No retry on 500 (not retryable)."""
        from agent_platform.llm.retry import async_retry

        call_count = 0

        async def mock_request():
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, text="Internal error")

        resp = await async_retry(mock_request, max_retries=3, base_delay=0.01)
        assert resp.status_code == 500
        assert call_count == 1  # no retry

    @pytest.mark.asyncio
    async def test_st_6_3_retry_on_timeout(self):
        """ST-6.3: Retry on timeout exception."""
        from agent_platform.llm.retry import async_retry

        call_count = 0

        async def mock_request():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ReadTimeout("timed out")
            return httpx.Response(200, json={"ok": True})

        resp = await async_retry(mock_request, max_retries=3, base_delay=0.01)
        assert resp.status_code == 200
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_st_6_4_hitl_timeout(self, tmp_path):
        """ST-6.4: HITL gate times out."""
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
            hitl_timeout_seconds=0.1,  # 100ms timeout
        )
        agent = Agent(name="timeout-agent", config=config)
        await agent_repo.create(agent)

        # LLM returns tool call, then text
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="tc-1",
                        name="some_tool",
                        arguments={},
                    )
                ],
                usage={},
            ),
            LLMResponse(content="Continued after timeout.", usage={}),
        ]

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
        )

        # Run — HITL gate should timeout (no one approves)
        response = await runtime.run(agent.id, "Do something")

        # Should have continued (tool denied by timeout)
        assert response.content is not None

        # Agent should be back to IDLE
        updated = await agent_repo.get(agent.id)
        assert updated is not None
        assert updated.status == AgentStatus.IDLE

        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_6_5_stuck_agent_cleanup(self, tmp_path):
        """ST-6.5: Stuck agent cleanup on startup."""
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
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        # Create stuck agents
        config = AgentConfig(model="test/model")
        running = Agent(name="stuck-running", config=config)
        running.status = AgentStatus.RUNNING
        await agent_repo.create(running)

        waiting = Agent(name="stuck-waiting", config=config)
        waiting.status = AgentStatus.WAITING_HITL
        await agent_repo.create(waiting)

        idle = Agent(name="normal-idle", config=config)
        await agent_repo.create(idle)

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=AsyncMock(),
            event_bus=InProcessEventBus(),
        )

        count = await runtime.cleanup_stuck_agents()
        assert count == 2

        # Verify all are IDLE now
        for agent_id in [running.id, waiting.id, idle.id]:
            a = await agent_repo.get(agent_id)
            assert a is not None
            assert a.status == AgentStatus.IDLE

        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_6_6_memory_prune(self, tmp_path):
        """ST-6.6: Memory prune deletes old low-importance memories."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.models import MemoryEntry, MemoryType

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        # Create old, low-importance memories
        for i in range(5):
            entry = MemoryEntry(
                agent_id="agent-1",
                content=f"Old memory {i}",
                memory_type=MemoryType.EPISODIC,
                importance=0.1,
                last_accessed_at=datetime.now(UTC) - timedelta(days=60),
            )
            await store.add(entry)

        # Create recent important memory
        recent = MemoryEntry(
            agent_id="agent-1",
            content="Recent important memory",
            memory_type=MemoryType.FACT,
            importance=0.9,
            last_accessed_at=datetime.now(UTC),
        )
        await store.add(recent)

        # Prune
        deleted = await store.prune("agent-1", threshold=0.3)
        assert deleted >= 1

        # Recent important memory should survive
        remaining = await store.list_by_agent("agent-1")
        contents = [m.content for m in remaining]
        assert "Recent important memory" in contents

    @pytest.mark.asyncio
    async def test_st_6_7_high_importance_survives(self, tmp_path):
        """ST-6.7: High-importance memories survive prune despite age."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.models import MemoryEntry, MemoryType

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        # Old but very important
        important = MemoryEntry(
            agent_id="agent-1",
            content="Critical knowledge",
            memory_type=MemoryType.FACT,
            importance=1.0,
            last_accessed_at=datetime.now(UTC) - timedelta(days=30),
            access_count=50,
        )
        await store.add(important)

        deleted = await store.prune("agent-1", threshold=0.1)
        assert deleted == 0

        remaining = await store.list_by_agent("agent-1")
        assert len(remaining) == 1
        assert remaining[0].content == "Critical knowledge"

    @pytest.mark.asyncio
    async def test_st_6_8_context_truncation(self):
        """ST-6.8: Context truncation under token budget."""
        from agent_platform.llm.models import Message, MessageRole
        from agent_platform.memory.token_estimator import (
            estimate_messages_tokens,
        )

        # Create a long conversation
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful."),
        ]
        for i in range(200):
            messages.append(
                Message(
                    role=MessageRole.HUMAN,
                    content=f"Message {i}: " + "x" * 200,
                )
            )

        # Full conversation is way over budget
        full_tokens = estimate_messages_tokens(messages)
        assert full_tokens > 1000

        # Use context manager's truncation directly
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.context_manager import ContextManager

        store = ChromaMemoryStore()
        ctx = ContextManager(
            memory_store=store,
            max_context_tokens=1000,
        )

        truncated = await ctx._compress(messages, 1000, "agent-1")

        # Should be under budget
        truncated_tokens = estimate_messages_tokens(truncated)
        assert truncated_tokens <= 1200  # some slack for marker

        # System prompt should be preserved
        assert truncated[0].role == MessageRole.SYSTEM
        assert truncated[0].content == "You are helpful."

        # Should have truncation marker
        marker = [
            m
            for m in truncated
            if m.role == MessageRole.SYSTEM and "truncated" in m.content
        ]
        assert len(marker) == 1

        # Should be shorter than original
        assert len(truncated) < len(messages)

    @pytest.mark.asyncio
    async def test_st_6_9_cost_aggregation(self, tmp_path):
        """ST-6.9: Cost aggregation from events."""
        from agent_platform.observation.cost_tracker import (
            compute_agent_cost,
        )
        from agent_platform.observation.cost_tracker import (
            configure as configure_costs,
        )
        from agent_platform.observation.events import Event, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        # Configure costs (normally done by app startup)
        configure_costs(
            model_costs={"openai/gpt-4.1-mini": [0.4, 1.6]},
            default_cost=[1.0, 4.0],
        )

        event_bus = InProcessEventBus(db_path=str(tmp_path / "events.db"))
        await event_bus.initialize()

        # Emit mock LLM_RESPONSE events
        await event_bus.emit(
            Event(
                agent_id="agent-1",
                event_type=EventType.LLM_RESPONSE,
                module="llm.openrouter",
                payload={
                    "model": "openai/gpt-4.1-mini",
                    "usage": {
                        "prompt_tokens": 1000,
                        "completion_tokens": 500,
                    },
                },
            )
        )
        await event_bus.emit(
            Event(
                agent_id="agent-1",
                event_type=EventType.LLM_RESPONSE,
                module="llm.openrouter",
                payload={
                    "model": "openai/gpt-4.1-mini",
                    "usage": {
                        "prompt_tokens": 2000,
                        "completion_tokens": 1000,
                    },
                },
            )
        )

        result = await compute_agent_cost(event_bus, "agent-1")

        assert result["total_prompt_tokens"] == 3000
        assert result["total_completion_tokens"] == 1500
        assert result["total_cost_usd"] > 0
        assert "openai/gpt-4.1-mini" in result["by_model"]
        assert result["by_model"]["openai/gpt-4.1-mini"]["calls"] == 2

        await event_bus.close()

    @pytest.mark.asyncio
    async def test_st_6_10_cost_api_endpoint(self, tmp_path):
        """ST-6.10: Cost API endpoint."""
        import httpx as httpx_mod

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings
        from agent_platform.observation.events import Event, EventType

        settings = Settings(
            openrouter_api_key="sk-test",  # type: ignore[arg-type]
        )
        app = create_app(settings, db_dir=str(tmp_path))

        async with app.router.lifespan_context(app):
            # Emit a test event directly
            event_bus = app.state.event_bus
            await event_bus.emit(
                Event(
                    agent_id="test-agent",
                    event_type=EventType.LLM_RESPONSE,
                    module="llm.openrouter",
                    payload={
                        "model": "openai/gpt-4.1-mini",
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 50,
                        },
                    },
                )
            )

            transport = httpx_mod.ASGITransport(app=app)
            async with httpx_mod.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Per-agent cost
                resp = await client.get("/agents/test-agent/cost")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total_prompt_tokens"] == 100
                assert data["total_cost_usd"] > 0

                # Total cost
                resp = await client.get("/cost")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total_prompt_tokens"] >= 100
