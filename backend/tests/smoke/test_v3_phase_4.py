"""
Smoke tests for V3 Phase 4 — Learning, Reflection & Capability Formalization.

All LLM and embedding calls are mocked.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent_platform.llm.models import LLMResponse

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v3-phase-4"),
]


class FakeEmbedding:
    def __init__(self, vectors=None):
        self._vectors = vectors or {}

    async def embed(self, texts):
        results = []
        for t in texts:
            if t in self._vectors:
                results.append(self._vectors[t])
            else:
                h = hash(t) % 1000
                results.append([h / 1000, (h * 7 % 1000) / 1000, (h * 13 % 1000) / 1000])
        return results


class FakeMemoryStore:
    """Minimal mock memory store for pattern tests."""

    def __init__(self):
        self._memories = []

    async def add(self, entry):
        self._memories.append(entry)

    async def search(self, query, top_k=5, **kwargs):
        return self._memories[:top_k]


class FakeEventBus:
    """Minimal mock event bus for analytics tests."""

    def __init__(self, events=None):
        self._events = events or []

    async def query(self, filters):
        results = []
        for e in self._events:
            if filters.event_types and e.event_type not in filters.event_types:
                continue
            results.append(e)
        return results


class TestV3Phase4:
    """ST-V3-4.x: Learning & Capability Formalization."""

    @pytest.mark.asyncio
    async def test_st_v3_4_1_analyze_capabilities(self, tmp_path):
        """ST-V3-4.1: analyze_capabilities returns structured report."""
        from agent_platform.tools.capability_tools import (
            CapabilityToolProvider,
        )
        from agent_platform.tools.skill_provider import SkillProvider

        # Set up a skill
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "summarize.md").write_text(
            "---\nname: summarize\n"
            "description: Summarize text\n---\n\nSummarize: {{text}}"
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Assessment: summarize skill available, "
            "no web scraping capability found.",
            usage={},
        )

        embeddings = FakeEmbedding({
            "Summarize text": [1.0, 0.0, 0.0],
            "summarize web content": [0.9, 0.1, 0.0],
        })

        skill_provider = SkillProvider(
            skills_dir=str(skills_dir),
            llm_provider=mock_llm,
            embedding_provider=embeddings,
        )

        provider = CapabilityToolProvider(
            llm_provider=mock_llm,
            skill_provider=skill_provider,
            embedding_provider=embeddings,
        )

        result = await provider.call_tool(
            "analyze_capabilities",
            {"task": "summarize web content"},
        )

        assert result.success
        data = json.loads(result.output)
        assert "available" in data
        assert "skills" in data["available"]
        assert "assessment" in data

    @pytest.mark.asyncio
    async def test_st_v3_4_2_graceful_without_embeddings(self, tmp_path):
        """ST-V3-4.2: analyze_capabilities without embeddings."""
        from agent_platform.tools.capability_tools import (
            CapabilityToolProvider,
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="No specific capabilities found.",
            usage={},
        )

        provider = CapabilityToolProvider(
            llm_provider=mock_llm,
        )

        result = await provider.call_tool(
            "analyze_capabilities",
            {"task": "do something"},
        )
        assert result.success

    def test_st_v3_4_3_capability_acquirer_template(self):
        """ST-V3-4.3: capability-acquirer template exists."""
        root = Path(__file__).resolve().parent.parent.parent.parent
        prompts = root / "prompts"

        json_path = prompts / "capability-acquirer.json"
        md_path = prompts / "capability-acquirer.md"

        assert json_path.exists()
        assert md_path.exists()

        config = json.loads(json_path.read_text())
        assert config.get("allowed_mcp_servers") == []

        prompt = md_path.read_text()
        assert "list_skills" in prompt
        assert "list_templates" in prompt

    @pytest.mark.asyncio
    async def test_st_v3_4_4_reflect_stores_retrospective(self):
        """ST-V3-4.4: reflect generates and stores retrospective."""
        from agent_platform.tools.capability_tools import (
            CapabilityToolProvider,
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Reflection: task completed successfully. "
            "The summarize skill was effective. "
            "Consider adding a web scraping tool next time.",
            usage={},
        )

        memory_store = FakeMemoryStore()

        provider = CapabilityToolProvider(
            llm_provider=mock_llm,
            memory_store=memory_store,
        )

        result = await provider.call_tool(
            "reflect",
            {
                "task": "Write a blog post about AI",
                "outcome": "Post written successfully",
                "tools_used": "summarize, spawn_agent(researcher)",
            },
        )

        assert result.success
        data = json.loads(result.output)
        assert "reflection" in data

        # Memory stored
        assert len(memory_store._memories) == 1
        mem = memory_store._memories[0]
        assert mem.memory_type.value == "procedure"

    def test_st_v3_4_5_reflect_prompt_exists(self):
        """ST-V3-4.5: reflect externalized prompt."""
        root = Path(__file__).resolve().parent.parent.parent.parent
        prompt_path = root / "prompts" / "system" / "reflect.md"

        assert prompt_path.exists()
        content = prompt_path.read_text()
        assert "task" in content.lower()
        assert "outcome" in content.lower()
        assert "tools" in content.lower()

    @pytest.mark.asyncio
    async def test_st_v3_4_6_tool_analytics(self):
        """ST-V3-4.6: tool_analytics aggregates from events."""
        from agent_platform.observation.events import Event, EventType
        from agent_platform.tools.capability_tools import (
            CapabilityToolProvider,
        )

        events = [
            Event(
                agent_id="a1",
                event_type=EventType.TOOL_CALL,
                module="core.runtime",
                payload={"tool_name": "summarize"},
            ),
            Event(
                agent_id="a1",
                event_type=EventType.TOOL_RESULT,
                module="core.runtime",
                payload={
                    "tool_name": "summarize",
                    "success": True,
                },
                duration_ms=150,
            ),
            Event(
                agent_id="a1",
                event_type=EventType.TOOL_CALL,
                module="core.runtime",
                payload={"tool_name": "summarize"},
            ),
            Event(
                agent_id="a1",
                event_type=EventType.TOOL_RESULT,
                module="core.runtime",
                payload={
                    "tool_name": "summarize",
                    "success": False,
                },
                duration_ms=200,
            ),
            Event(
                agent_id="a1",
                event_type=EventType.TOOL_CALL,
                module="core.runtime",
                payload={"tool_name": "recall"},
            ),
            Event(
                agent_id="a1",
                event_type=EventType.TOOL_RESULT,
                module="core.runtime",
                payload={
                    "tool_name": "recall",
                    "success": True,
                },
                duration_ms=50,
            ),
        ]

        event_bus = FakeEventBus(events)

        provider = CapabilityToolProvider(
            llm_provider=AsyncMock(),
            event_bus=event_bus,
        )

        # All tools
        result = await provider.call_tool(
            "tool_analytics", {},
        )
        assert result.success
        data = json.loads(result.output)
        assert len(data) >= 2
        # summarize should have 2 calls
        summ = next(
            (t for t in data if t["tool_name"] == "summarize"),
            None,
        )
        assert summ is not None
        assert summ["call_count"] == 2
        assert summ["success_rate"] == 0.5

        # Specific tool
        result2 = await provider.call_tool(
            "tool_analytics",
            {"tool_name": "recall"},
        )
        data2 = json.loads(result2.output)
        assert len(data2) == 1
        assert data2[0]["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_st_v3_4_7_store_pattern(self):
        """ST-V3-4.7: store_pattern stores a PROCEDURE memory."""
        from agent_platform.tools.capability_tools import (
            CapabilityToolProvider,
        )

        memory_store = FakeMemoryStore()

        provider = CapabilityToolProvider(
            llm_provider=AsyncMock(),
            memory_store=memory_store,
        )

        result = await provider.call_tool(
            "store_pattern",
            {
                "task_type": "competitive analysis",
                "strategy": "parallel",
                "subtasks": json.dumps([
                    "Research company A",
                    "Research company B",
                    "Research company C",
                ]),
                "notes": "Each company researched independently",
            },
        )

        assert result.success
        assert len(memory_store._memories) == 1
        mem = memory_store._memories[0]
        assert mem.memory_type.value == "procedure"
        assert "competitive analysis" in mem.content
        assert "parallel" in mem.content

    @pytest.mark.asyncio
    async def test_st_v3_4_8_find_pattern(self):
        """ST-V3-4.8: find_pattern retrieves matching patterns."""
        from agent_platform.memory.models import MemoryEntry, MemoryType
        from agent_platform.tools.capability_tools import (
            CapabilityToolProvider,
        )

        memory_store = FakeMemoryStore()
        # Pre-populate
        memory_store._memories.append(
            MemoryEntry(
                id="p1",
                agent_id="sys",
                content=(
                    "Pattern: competitive analysis\n"
                    "Strategy: parallel\n"
                    "Subtasks: research each company independently"
                ),
                memory_type=MemoryType.PROCEDURE,
                importance=0.8,
            )
        )

        provider = CapabilityToolProvider(
            llm_provider=AsyncMock(),
            memory_store=memory_store,
        )

        result = await provider.call_tool(
            "find_pattern",
            {"task_description": "compare three products"},
        )

        assert result.success
        data = json.loads(result.output)
        assert len(data) >= 1
        assert "competitive analysis" in data[0]["content"]

    @pytest.mark.asyncio
    async def test_st_v3_4_9_app_integration(self, tmp_path):
        """ST-V3-4.9: Tools registered in create_app."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "default.md").write_text(
            "You are a helpful assistant.",
        )
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        (tmp_path / "lyra.config.json").write_text(
            json.dumps({
                "dataDir": str(tmp_path / "data"),
                "systemPromptsDir": str(prompts_dir),
                "skillsDir": str(skills_dir),
                "defaultModel": "test-model",
            }),
        )

        settings = Settings(openrouter_api_key="sk-test")
        app = create_app(
            settings,
            db_dir=str(tmp_path / "data"),
            project_root=tmp_path,
        )

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get("/tools")
                assert resp.status_code == 200
                names = [t["name"] for t in resp.json()]
                assert "analyze_capabilities" in names
                assert "reflect" in names
                assert "tool_analytics" in names
                assert "store_pattern" in names
                assert "find_pattern" in names
