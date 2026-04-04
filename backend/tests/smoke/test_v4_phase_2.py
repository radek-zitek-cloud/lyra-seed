"""
Smoke tests for V4 Phase 2 — RAG Knowledge Base.

All embedding calls are mocked.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v4-phase-2"),
]


def _write_doc(d: Path, name: str, content: str) -> Path:
    p = d / name
    p.write_text(content, encoding="utf-8")
    return p


SAMPLE_DOC = """\
# Memory System

The memory system has three tiers.

## Context Memory

Context memory manages the current conversation window.
It handles token budgets and compression.

## Cross-Context Memory

Cross-context memory persists across conversations.
It stores session summaries and user preferences.

### Semantic Search

Memories are retrieved via embedding similarity.

## Long-Term Memory

Long-term memory stores facts and procedures.
"""


class TestV4Phase2:
    """ST-V4-2.x: RAG Knowledge Base."""

    def test_st_v4_2_1_chunker_splits_by_headings(self, tmp_path):
        """ST-V4-2.1: Markdown chunker splits by headings."""
        from agent_platform.knowledge.chunker import chunk_markdown

        path = _write_doc(tmp_path, "memory.md", SAMPLE_DOC)
        chunks = chunk_markdown(path)

        assert len(chunks) >= 4  # intro + 3 sections minimum
        # Each chunk has source and heading
        for c in chunks:
            assert c.source == "memory.md"
            assert c.content
            assert c.heading_path

        # Check nested heading
        semantic = [c for c in chunks if "Semantic Search" in c.heading_path]
        assert len(semantic) == 1
        assert "Cross-Context Memory" in semantic[0].heading_path

    def test_st_v4_2_2_store_ingest_and_search(self, tmp_path):
        """ST-V4-2.2: KnowledgeStore ingests and searches."""
        from agent_platform.knowledge.store import KnowledgeStore

        store = KnowledgeStore(persist_dir=str(tmp_path / "kb"))
        path = _write_doc(tmp_path, "test.md", SAMPLE_DOC)
        store.ingest(path)

        results = store.search("token budget compression", top_k=3)
        assert len(results) >= 1
        assert any("Context Memory" in r.heading_path for r in results)

    def test_st_v4_2_3_reingest_replaces(self, tmp_path):
        """ST-V4-2.3: Re-ingesting replaces chunks."""
        from agent_platform.knowledge.store import KnowledgeStore

        store = KnowledgeStore(persist_dir=str(tmp_path / "kb"))
        path = _write_doc(tmp_path, "doc.md", "# Old\n\nOld content.")
        store.ingest(path)

        results = store.search("Old content", top_k=1)
        assert len(results) >= 1

        # Re-write and re-ingest
        _write_doc(tmp_path, "doc.md", "# New\n\nBrand new content.")
        store.ingest(path)

        old = store.search("Old content", top_k=1)
        new = store.search("Brand new content", top_k=1)
        # New content should be findable
        assert any("Brand new" in r.content for r in new)

    @pytest.mark.asyncio
    async def test_st_v4_2_4_search_knowledge_tool(self, tmp_path):
        """ST-V4-2.4: search_knowledge tool returns results."""
        from agent_platform.knowledge.store import KnowledgeStore
        from agent_platform.knowledge.tools import KnowledgeToolProvider

        store = KnowledgeStore(persist_dir=str(tmp_path / "kb"))
        path = _write_doc(tmp_path, "test.md", SAMPLE_DOC)
        store.ingest(path)

        provider = KnowledgeToolProvider(knowledge_store=store)
        result = await provider.call_tool(
            "search_knowledge",
            {"query": "semantic search memories"},
        )

        assert result.success
        data = json.loads(result.output)
        assert len(data) >= 1
        assert "content" in data[0]
        assert "source" in data[0]
        assert "heading_path" in data[0]

    @pytest.mark.asyncio
    async def test_st_v4_2_5_ingest_document_tool(self, tmp_path):
        """ST-V4-2.5: ingest_document tool indexes a file."""
        from agent_platform.knowledge.store import KnowledgeStore
        from agent_platform.knowledge.tools import KnowledgeToolProvider

        store = KnowledgeStore(persist_dir=str(tmp_path / "kb"))
        path = _write_doc(tmp_path, "new.md", "# New Doc\n\nNew content here.")

        provider = KnowledgeToolProvider(knowledge_store=store)

        result = await provider.call_tool(
            "ingest_document",
            {"path": str(path)},
        )
        assert result.success
        data = json.loads(result.output)
        assert data["chunks"] >= 1

        # Reject non-.md
        txt_path = _write_doc(tmp_path, "file.txt", "Not markdown")
        result2 = await provider.call_tool(
            "ingest_document",
            {"path": str(txt_path)},
        )
        assert not result2.success

        # Reject nonexistent
        result3 = await provider.call_tool(
            "ingest_document",
            {"path": "/nonexistent/file.md"},
        )
        assert not result3.success

    def test_st_v4_2_6_directory_scanning(self, tmp_path):
        """ST-V4-2.6: Directory scanning at startup."""
        from agent_platform.knowledge.store import KnowledgeStore

        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()
        _write_doc(kb_dir, "doc1.md", "# Doc 1\n\nFirst document.")
        _write_doc(kb_dir, "doc2.md", "# Doc 2\n\nSecond document.")
        _write_doc(kb_dir, "readme.txt", "Not a markdown file")

        store = KnowledgeStore(persist_dir=str(tmp_path / "kb"))
        store.ingest_directory(kb_dir)

        sources = store.get_sources()
        assert "doc1.md" in sources
        assert "doc2.md" in sources
        assert "readme.txt" not in sources

    def test_st_v4_2_7_platform_config(self):
        """ST-V4-2.7: PlatformConfig has knowledgeDir."""
        from agent_platform.core.platform_config import PlatformConfig

        config = PlatformConfig()
        assert config.knowledgeDir == "./knowledge"

    @pytest.mark.asyncio
    async def test_st_v4_2_8_app_integration(self, tmp_path):
        """ST-V4-2.8: Tools registered in create_app."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "default.md").write_text("You are a helpful assistant.")
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir()

        (tmp_path / "lyra.config.json").write_text(json.dumps({
            "dataDir": str(tmp_path / "data"),
            "systemPromptsDir": str(prompts_dir),
            "skillsDir": str(skills_dir),
            "knowledgeDir": str(kb_dir),
            "defaultModel": "test-model",
        }))

        settings = Settings(openrouter_api_key="sk-test")
        app = create_app(
            settings, db_dir=str(tmp_path / "data"), project_root=tmp_path,
        )

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get("/tools")
                names = [t["name"] for t in resp.json()]
                assert "search_knowledge" in names
                assert "ingest_document" in names

    @pytest.mark.asyncio
    async def test_st_v4_2_9_analyze_includes_knowledge(self, tmp_path):
        """ST-V4-2.9: analyze_capabilities includes knowledge."""
        from agent_platform.knowledge.store import KnowledgeStore
        from agent_platform.llm.models import LLMResponse
        from agent_platform.tools.capability_tools import CapabilityToolProvider

        store = KnowledgeStore(persist_dir=str(tmp_path / "kb"))
        path = _write_doc(tmp_path, "arch.md", SAMPLE_DOC)
        store.ingest(path)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Knowledge base has memory system docs.", usage={},
        )

        provider = CapabilityToolProvider(
            llm_provider=mock_llm,
            knowledge_store=store,
        )

        result = await provider.call_tool(
            "analyze_capabilities",
            {"task": "explain the memory system architecture"},
        )

        assert result.success
        data = json.loads(result.output)
        assert "available" in data
        assert "relevant_knowledge" in data["available"]
        assert len(data["available"]["relevant_knowledge"]) >= 1
