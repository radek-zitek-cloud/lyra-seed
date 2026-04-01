"""
Smoke tests for V1 Phase 4 — Memory System.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
All LLM and embedding calls are mocked.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-4"),
]


class TestV1Phase4:
    """ST-4.x: Memory System smoke tests."""

    def test_st_4_1_memory_entry_model(self):
        """ST-4.1: MemoryEntry model and MemoryType."""
        from agent_platform.memory.models import MemoryEntry, MemoryType

        # MemoryType enum values
        assert MemoryType.EPISODIC is not None
        assert MemoryType.PREFERENCE is not None
        assert MemoryType.DECISION is not None
        assert MemoryType.OUTCOME is not None
        assert MemoryType.FACT is not None
        assert MemoryType.PROCEDURE is not None

        # Create entry with defaults
        entry = MemoryEntry(
            agent_id="agent-1",
            content="The user prefers concise answers.",
            memory_type=MemoryType.PREFERENCE,
        )
        assert entry.id is not None
        assert entry.created_at is not None
        assert entry.last_accessed_at is not None
        assert entry.importance == 0.5  # default
        assert entry.decay_score == 1.0  # default
        assert entry.access_count == 0

        # Create with custom importance
        entry2 = MemoryEntry(
            agent_id="agent-1",
            content="Critical fact",
            memory_type=MemoryType.FACT,
            importance=0.9,
        )
        assert entry2.importance == 0.9

    @pytest.mark.asyncio
    async def test_st_4_2_memory_store_crud_and_search(self, tmp_path):
        """ST-4.2: Memory store CRUD and search."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.models import MemoryEntry, MemoryType

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        # Create entries
        e1 = MemoryEntry(
            agent_id="agent-1",
            content="Python is a programming language",
            memory_type=MemoryType.FACT,
            importance=0.8,
        )
        e2 = MemoryEntry(
            agent_id="agent-1",
            content="The user likes detailed explanations",
            memory_type=MemoryType.PREFERENCE,
            importance=0.6,
        )
        e3 = MemoryEntry(
            agent_id="agent-2",
            content="JavaScript runs in browsers",
            memory_type=MemoryType.FACT,
            importance=0.7,
        )

        await store.add(e1)
        await store.add(e2)
        await store.add(e3)

        # Get by ID
        fetched = await store.get(e1.id)
        assert fetched is not None
        assert fetched.content == "Python is a programming language"
        assert fetched.memory_type == MemoryType.FACT

        # List by agent_id
        agent1_memories = await store.list_by_agent("agent-1")
        assert len(agent1_memories) == 2

        # Search — should find Python-related memory
        results = await store.search(
            query="What programming language is Python?",
            agent_id="agent-1",
            top_k=2,
        )
        assert len(results) >= 1
        # The Python entry should rank higher than the preferences one
        assert results[0].content == "Python is a programming language"

        # Search with memory_type filter
        results = await store.search(
            query="user preferences",
            agent_id="agent-1",
            memory_type=MemoryType.PREFERENCE,
            top_k=5,
        )
        assert len(results) >= 1
        assert all(r.memory_type == MemoryType.PREFERENCE for r in results)

        # Delete
        deleted = await store.delete(e1.id)
        assert deleted is True
        assert await store.get(e1.id) is None

    def test_st_4_3_fake_embedding_provider(self):
        """ST-4.3: Fake embedding provider."""
        from agent_platform.memory.fake_embeddings import (
            FakeEmbeddingProvider,
        )

        provider = FakeEmbeddingProvider(dimensions=64)

        # Same text produces same embedding
        vec1 = provider.embed_text("hello world")
        vec2 = provider.embed_text("hello world")
        assert vec1 == vec2

        # Different texts produce different embeddings
        vec3 = provider.embed_text("goodbye world")
        assert vec1 != vec3

        # Consistent dimensionality
        assert len(vec1) == 64
        assert len(vec3) == 64

        # Batch embed
        vecs = provider.embed_batch(["foo", "bar", "baz"])
        assert len(vecs) == 3
        assert all(len(v) == 64 for v in vecs)

    def test_st_4_4_time_decay_strategy(self):
        """ST-4.4: Time decay strategy."""
        from agent_platform.memory.decay import TimeDecayStrategy
        from agent_platform.memory.models import MemoryEntry, MemoryType

        strategy = TimeDecayStrategy(half_life_days=7.0)

        # Recent memory — high score
        recent = MemoryEntry(
            agent_id="a",
            content="recent",
            memory_type=MemoryType.EPISODIC,
            last_accessed_at=datetime.now(UTC),
            importance=0.5,
        )
        score_recent = strategy.compute(recent)
        assert 0.0 <= score_recent <= 1.0

        # Old memory — lower score
        old = MemoryEntry(
            agent_id="a",
            content="old",
            memory_type=MemoryType.EPISODIC,
            last_accessed_at=datetime.now(UTC) - timedelta(days=30),
            importance=0.5,
        )
        score_old = strategy.compute(old)
        assert score_old < score_recent

        # Frequently accessed — decays slower
        frequent = MemoryEntry(
            agent_id="a",
            content="frequent",
            memory_type=MemoryType.EPISODIC,
            last_accessed_at=datetime.now(UTC) - timedelta(days=30),
            importance=0.5,
            access_count=50,
        )
        score_frequent = strategy.compute(frequent)
        assert score_frequent > score_old

        # High importance — decays slower
        important = MemoryEntry(
            agent_id="a",
            content="important",
            memory_type=MemoryType.EPISODIC,
            last_accessed_at=datetime.now(UTC) - timedelta(days=30),
            importance=1.0,
        )
        score_important = strategy.compute(important)
        assert score_important > score_old

        # All scores in range
        for s in [score_recent, score_old, score_frequent, score_important]:
            assert 0.0 <= s <= 1.0

    @pytest.mark.asyncio
    async def test_st_4_5_memory_tools(self, tmp_path):
        """ST-4.5: Memory tools (remember, recall, forget)."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.memory_tools import MemoryToolProvider
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))
        event_bus = InProcessEventBus()

        provider = MemoryToolProvider(
            memory_store=store,
            event_bus=event_bus,
        )

        # List tools
        tools = await provider.list_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == {"remember", "recall", "forget"}

        # Remember
        result = await provider.call_tool(
            "remember",
            {
                "content": "The capital of France is Paris",
                "memory_type": "fact",
                "importance": 0.8,
                "agent_id": "agent-1",
            },
        )
        assert result.success is True
        memory_id = result.output
        assert isinstance(memory_id, str)

        # Recall
        result = await provider.call_tool(
            "recall",
            {
                "query": "What is the capital of France?",
                "agent_id": "agent-1",
                "top_k": 3,
            },
        )
        assert result.success is True
        assert "Paris" in str(result.output)

        # Forget
        result = await provider.call_tool(
            "forget",
            {"memory_id": memory_id},
        )
        assert result.success is True

        # Verify forgotten
        result = await provider.call_tool(
            "recall",
            {
                "query": "capital of France",
                "agent_id": "agent-1",
                "top_k": 3,
            },
        )
        # Should return empty or not contain Paris
        assert "Paris" not in str(result.output)

    @pytest.mark.asyncio
    async def test_st_4_6_context_manager(self, tmp_path):
        """ST-4.6: Context manager injects memories."""
        from agent_platform.llm.models import Message, MessageRole
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.context_manager import ContextManager
        from agent_platform.memory.models import MemoryEntry, MemoryType

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        # Store some memories
        await store.add(
            MemoryEntry(
                agent_id="agent-1",
                content="Python was created by Guido van Rossum",
                memory_type=MemoryType.FACT,
                importance=0.9,
            )
        )
        await store.add(
            MemoryEntry(
                agent_id="agent-1",
                content="The user prefers code examples",
                memory_type=MemoryType.PREFERENCE,
                importance=0.7,
            )
        )

        ctx_manager = ContextManager(memory_store=store, top_k=5)

        # Assemble context with relevant query
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful."),
            Message(
                role=MessageRole.HUMAN,
                content="Tell me about Python",
            ),
        ]

        assembled = await ctx_manager.assemble(
            agent_id="agent-1",
            messages=messages,
            query="Tell me about Python",
        )

        # Should have injected a memory message
        assert len(assembled) > len(messages)
        # Find the injected memory message
        memory_msgs = [
            m
            for m in assembled
            if m.role == MessageRole.SYSTEM and "memor" in m.content.lower()
        ]
        assert len(memory_msgs) >= 1
        assert "Guido" in memory_msgs[0].content

        # With no matching memories (different agent)
        assembled2 = await ctx_manager.assemble(
            agent_id="agent-999",
            messages=messages,
            query="Tell me about Python",
        )
        # Should not inject anything
        assert len(assembled2) == len(messages)

    @pytest.mark.asyncio
    async def test_st_4_7_runtime_integrates_memory(self, tmp_path):
        """ST-4.7: Runtime integrates memory."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.context_manager import ContextManager
        from agent_platform.memory.memory_tools import MemoryToolProvider
        from agent_platform.memory.models import MemoryEntry, MemoryType
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.registry import ToolRegistry

        event_bus = InProcessEventBus(db_path=str(tmp_path / "events.db"))
        await event_bus.initialize()

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        memory_store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))
        ctx_manager = ContextManager(memory_store=memory_store, top_k=3)
        memory_tools = MemoryToolProvider(
            memory_store=memory_store, event_bus=event_bus
        )

        # Pre-seed a memory
        await memory_store.add(
            MemoryEntry(
                agent_id="will-set-later",
                content="User prefers short answers",
                memory_type=MemoryType.PREFERENCE,
                importance=0.8,
            )
        )

        registry = ToolRegistry()
        registry.register_provider(memory_tools)

        config = AgentConfig(model="test/model")
        agent = Agent(name="memory-agent", config=config)
        await agent_repo.create(agent)

        # Update the memory's agent_id to match
        memories = await memory_store.list_by_agent("will-set-later")
        for m in memories:
            await memory_store.delete(m.id)
        await memory_store.add(
            MemoryEntry(
                agent_id=agent.id,
                content="User prefers short answers",
                memory_type=MemoryType.PREFERENCE,
                importance=0.8,
            )
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Here is a short answer.",
            usage={},
        )

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=registry,
            context_manager=ctx_manager,
        )

        response = await runtime.run(agent.id, "How does Python work?")
        assert response.content == "Here is a short answer."

        # Memory tools should be in the tool list
        tools_schema = await registry.get_tools_schema()
        tool_names = {t["function"]["name"] for t in tools_schema}
        assert "remember" in tool_names
        assert "recall" in tool_names
        assert "forget" in tool_names

        # Check the LLM was called with injected memories
        call_args = mock_llm.complete.call_args
        messages = call_args[0][0]
        # There should be a memory injection message
        memory_content = " ".join(
            m.content for m in messages if isinstance(m.content, str)
        )
        assert "short answers" in memory_content

        # Check for MEMORY_READ event
        events = await event_bus.query(EventFilter(agent_id=agent.id))
        event_types = [e.event_type for e in events]
        assert EventType.MEMORY_READ in event_types

        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()
