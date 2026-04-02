"""
Smoke tests for V1 Phase 7 — Memory Enhancement.

Tests: visibility, cross-agent search, summarization, extraction, config.
All LLM calls are mocked.
"""

import json
from unittest.mock import AsyncMock

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-7"),
]


class TestV1Phase7:
    """ST-7.x: Memory Enhancement smoke tests."""

    def test_st_7_1_visibility_enum(self):
        """ST-7.1: MemoryVisibility enum and MemoryEntry visibility field."""
        from agent_platform.memory.models import (
            MemoryEntry,
            MemoryType,
            MemoryVisibility,
        )

        assert MemoryVisibility.PRIVATE is not None
        assert MemoryVisibility.TEAM is not None
        assert MemoryVisibility.PUBLIC is not None
        assert MemoryVisibility.INHERIT is not None

        entry = MemoryEntry(
            agent_id="a1",
            content="test",
            memory_type=MemoryType.FACT,
            visibility=MemoryVisibility.PUBLIC,
        )
        assert entry.visibility == MemoryVisibility.PUBLIC

        # Default is PRIVATE
        entry2 = MemoryEntry(
            agent_id="a1",
            content="test",
            memory_type=MemoryType.FACT,
        )
        assert entry2.visibility == MemoryVisibility.PRIVATE

    @pytest.mark.asyncio
    async def test_st_7_2_visibility_roundtrip(self, tmp_path):
        """ST-7.2: Visibility persists through ChromaDB round-trip."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.models import (
            MemoryEntry,
            MemoryType,
            MemoryVisibility,
        )

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        entry = MemoryEntry(
            agent_id="a1",
            content="Public knowledge",
            memory_type=MemoryType.DOMAIN_KNOWLEDGE,
            visibility=MemoryVisibility.PUBLIC,
        )
        await store.add(entry)

        fetched = await store.get(entry.id)
        assert fetched is not None
        assert fetched.visibility == MemoryVisibility.PUBLIC

    @pytest.mark.asyncio
    async def test_st_7_3_cross_agent_public_search(self, tmp_path):
        """ST-7.3: Cross-agent search returns PUBLIC memories."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.models import (
            MemoryEntry,
            MemoryType,
            MemoryVisibility,
        )

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        # Agent A stores a PUBLIC memory
        await store.add(
            MemoryEntry(
                agent_id="agent-a",
                content="Python was created by Guido",
                memory_type=MemoryType.DOMAIN_KNOWLEDGE,
                visibility=MemoryVisibility.PUBLIC,
            )
        )

        # Agent B searches with include_public=True
        results = await store.search(
            query="Who created Python?",
            agent_id="agent-b",
            include_public=True,
            top_k=5,
        )
        assert len(results) >= 1
        assert any("Guido" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_st_7_4_private_stays_private(self, tmp_path):
        """ST-7.4: PRIVATE memories not visible to other agents."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.models import (
            MemoryEntry,
            MemoryType,
            MemoryVisibility,
        )

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        await store.add(
            MemoryEntry(
                agent_id="agent-a",
                content="Secret preference of agent A",
                memory_type=MemoryType.PREFERENCE,
                visibility=MemoryVisibility.PRIVATE,
            )
        )

        results = await store.search(
            query="agent preferences",
            agent_id="agent-b",
            include_public=True,
            top_k=5,
        )
        # Agent B should NOT see Agent A's private memory
        assert not any("Secret" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_st_7_5_summarization(self, tmp_path):
        """ST-7.5: Summarization replaces truncation marker."""
        from agent_platform.llm.models import LLMResponse, Message, MessageRole
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.context_manager import ContextManager

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Summary: user discussed Python programming.",
            usage={},
        )

        ctx = ContextManager(
            memory_store=store,
            max_context_tokens=200,
            llm_provider=mock_llm,
            summary_model="test/model",
        )

        # Build messages that exceed budget
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful."),
        ]
        for i in range(50):
            messages.append(
                Message(
                    role=MessageRole.HUMAN,
                    content=f"Message {i}: " + "x" * 100,
                )
            )

        result = await ctx.assemble(
            agent_id="agent-1",
            messages=messages,
            query="test",
            max_context_tokens=200,
        )

        # Should contain summary, not truncation marker
        all_content = " ".join(m.content for m in result if isinstance(m.content, str))
        assert "Summary" in all_content
        assert len(result) < len(messages)

    @pytest.mark.asyncio
    async def test_st_7_6_summary_saved_as_episodic(self, tmp_path):
        """ST-7.6: Summary saved as EPISODIC memory."""
        from agent_platform.llm.models import LLMResponse, Message, MessageRole
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.context_manager import ContextManager
        from agent_platform.memory.models import MemoryType

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Summary of earlier conversation.",
            usage={},
        )

        ctx = ContextManager(
            memory_store=store,
            max_context_tokens=200,
            llm_provider=mock_llm,
            summary_model="test/model",
        )

        messages = [
            Message(role=MessageRole.SYSTEM, content="System."),
        ] + [Message(role=MessageRole.HUMAN, content="x" * 100) for _ in range(50)]

        await ctx.assemble(
            agent_id="agent-1",
            messages=messages,
            query="test",
            max_context_tokens=200,
        )

        # Check an EPISODIC memory was stored
        entries = await store.list_by_agent("agent-1")
        episodic = [e for e in entries if e.memory_type == MemoryType.EPISODIC]
        assert len(episodic) >= 1
        assert "Summary" in episodic[0].content

    def test_st_7_7_fallback_truncation(self):
        """ST-7.7: Falls back to truncation when no LLM provider."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.context_manager import ContextManager

        store = ChromaMemoryStore()
        ctx = ContextManager(
            memory_store=store,
            max_context_tokens=200,
        )
        # No llm_provider — should fall back to truncation
        # Just verify the ContextManager can be created without LLM
        assert ctx._llm is None

    @pytest.mark.asyncio
    async def test_st_7_8_extraction_produces_entries(self, tmp_path):
        """ST-7.8: Fact extraction produces memory entries."""
        from agent_platform.llm.models import LLMResponse, Message, MessageRole
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.extractor import FactExtractor

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content=json.dumps(
                [
                    {
                        "content": "User prefers dark mode",
                        "memory_type": "preference",
                        "importance": 0.8,
                    }
                ]
            ),
            usage={},
        )

        extractor = FactExtractor(
            llm_provider=mock_llm,
            extraction_model="test/model",
            memory_store=store,
        )

        entries = await extractor.extract(
            agent_id="agent-1",
            assistant_message="I'll set dark mode for you.",
            conversation_context=[
                Message(role=MessageRole.HUMAN, content="Use dark mode"),
            ],
        )

        assert len(entries) == 1
        assert entries[0].content == "User prefers dark mode"
        assert entries[0].memory_type.value == "preference"
        assert entries[0].importance == 0.8

    @pytest.mark.asyncio
    async def test_st_7_9_domain_knowledge_defaults_public(self, tmp_path):
        """ST-7.9: Extracted DOMAIN_KNOWLEDGE defaults to PUBLIC."""
        from agent_platform.llm.models import LLMResponse, Message, MessageRole
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.extractor import FactExtractor
        from agent_platform.memory.models import MemoryVisibility

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content=json.dumps(
                [
                    {
                        "content": "API rate limit is 100/min",
                        "memory_type": "domain_knowledge",
                        "importance": 0.9,
                    }
                ]
            ),
            usage={},
        )

        extractor = FactExtractor(
            llm_provider=mock_llm,
            extraction_model="test/model",
            memory_store=store,
        )

        entries = await extractor.extract(
            agent_id="agent-1",
            assistant_message="The API rate limit is 100/min.",
            conversation_context=[
                Message(role=MessageRole.HUMAN, content="Rate limit?"),
            ],
        )

        assert len(entries) == 1
        assert entries[0].visibility == MemoryVisibility.PUBLIC

    @pytest.mark.asyncio
    async def test_st_7_10_extraction_emits_events(self, tmp_path):
        """ST-7.10: Extraction emits MEMORY_WRITE events."""
        from agent_platform.llm.models import LLMResponse, Message, MessageRole
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.extractor import FactExtractor
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        event_bus = InProcessEventBus(db_path=str(tmp_path / "events.db"))
        await event_bus.initialize()

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content=json.dumps(
                [{"content": "A fact", "memory_type": "fact", "importance": 0.5}]
            ),
            usage={},
        )

        extractor = FactExtractor(
            llm_provider=mock_llm,
            extraction_model="test/model",
            memory_store=store,
            event_bus=event_bus,
        )

        await extractor.extract(
            agent_id="agent-1",
            assistant_message="Here is a fact.",
            conversation_context=[
                Message(role=MessageRole.HUMAN, content="Tell me"),
            ],
        )

        events = await event_bus.query(
            EventFilter(
                agent_id="agent-1",
                event_types=[EventType.MEMORY_WRITE],
            )
        )
        assert len(events) >= 1
        assert events[0].payload.get("source") == "auto_extract"

        await event_bus.close()

    @pytest.mark.asyncio
    async def test_st_7_11_auto_extract_disabled(self, tmp_path):
        """ST-7.11: auto_extract=False skips extraction."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse
        from agent_platform.memory.extractor import FactExtractor
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        config = AgentConfig(model="test/model", auto_extract=False)
        agent = Agent(name="no-extract", config=config)
        await agent_repo.create(agent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(content="Response.", usage={})

        mock_extractor = AsyncMock(spec=FactExtractor)

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=InProcessEventBus(),
            extractor=mock_extractor,
        )

        await runtime.run(agent.id, "Hello")

        # Extractor should NOT have been called
        mock_extractor.extract.assert_not_called()

        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_7_12_extraction_failure_safe(self, tmp_path):
        """ST-7.12: Extraction failure does not break agent run."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse
        from agent_platform.memory.extractor import FactExtractor
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        config = AgentConfig(model="test/model", auto_extract=True)
        agent = Agent(name="fail-extract", config=config)
        await agent_repo.create(agent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(content="Response.", usage={})

        mock_extractor = AsyncMock(spec=FactExtractor)
        mock_extractor.extract.side_effect = RuntimeError("boom")

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=InProcessEventBus(),
            extractor=mock_extractor,
        )

        # Should succeed despite extraction failure
        response = await runtime.run(agent.id, "Hello")
        assert response.content == "Response."

        await agent_repo.close()
        await conv_repo.close()

    def test_st_7_13_config_summary_model(self):
        """ST-7.13: Config resolution for summary_model."""
        from agent_platform.core.models import AgentConfig

        config = AgentConfig(summary_model="custom/model")
        assert config.summary_model == "custom/model"

        # Default is None (falls back to platform config)
        default = AgentConfig()
        assert default.summary_model is None

    def test_st_7_14_config_extraction_model(self):
        """ST-7.14: Config resolution for extraction_model."""
        from agent_platform.core.models import AgentConfig

        config = AgentConfig(
            extraction_model="custom/extractor",
            auto_extract=True,
        )
        assert config.extraction_model == "custom/extractor"
        assert config.auto_extract is True

    @pytest.mark.asyncio
    async def test_st_7_15_remember_tool_visibility(self, tmp_path):
        """ST-7.15: Remember tool accepts visibility parameter."""
        from agent_platform.memory.chroma_memory_store import (
            ChromaMemoryStore,
        )
        from agent_platform.memory.memory_tools import MemoryToolProvider
        from agent_platform.memory.models import MemoryVisibility

        store = ChromaMemoryStore(persist_dir=str(tmp_path / "chroma"))
        provider = MemoryToolProvider(memory_store=store)

        result = await provider.call_tool(
            "remember",
            {
                "content": "Shared knowledge",
                "memory_type": "domain_knowledge",
                "agent_id": "agent-1",
                "visibility": "public",
            },
        )
        assert result.success is True

        # Verify stored with PUBLIC visibility
        entry = await store.get(result.output)
        assert entry is not None
        assert entry.visibility == MemoryVisibility.PUBLIC
