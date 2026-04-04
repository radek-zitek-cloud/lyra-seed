"""
Smoke tests for V4 Phase 3 — Unified Capability Discovery.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent_platform.llm.models import LLMResponse

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v4-phase-3"),
]


def _write_skill(d, name, desc, template):
    (d / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n"
        f"parameters:\n  text:\n    type: string\n---\n\n{template}"
    )


def _write_doc(d, name, content):
    (d / name).write_text(content)


class TestV4Phase3:
    """ST-V4-3.x: Unified Capability Discovery."""

    @pytest.mark.asyncio
    async def test_st_v4_3_1_multi_source_discover(self, tmp_path):
        """ST-V4-3.1: discover returns results from multiple sources."""
        from agent_platform.knowledge.store import KnowledgeStore
        from agent_platform.tools.discovery_provider import DiscoveryProvider
        from agent_platform.tools.skill_provider import SkillProvider

        # Set up skills
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "summarize", "Summarize text", "Sum: {{text}}")

        skill_provider = SkillProvider(
            skills_dir=str(skills_dir), llm_provider=AsyncMock(),
        )

        # Set up knowledge
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        kb = KnowledgeStore(persist_dir=str(tmp_path / "kb_index"))
        _write_doc(kb_dir, "guide.md", "# Summarization\n\nHow to summarize text effectively.")
        kb.ingest(kb_dir / "guide.md")

        provider = DiscoveryProvider(
            skill_provider=skill_provider,
            knowledge_store=kb,
        )

        result = await provider.call_tool("discover", {"query": "summarize text"})
        assert result.success
        data = json.loads(result.output)
        assert len(data) >= 2

        types = {r["type"] for r in data}
        assert len(types) >= 2  # at least skill + knowledge
        assert data[0]["score"] >= data[-1]["score"]  # sorted

    @pytest.mark.asyncio
    async def test_st_v4_3_2_source_filtering(self, tmp_path):
        """ST-V4-3.2: discover with source filtering."""
        from agent_platform.knowledge.store import KnowledgeStore
        from agent_platform.tools.discovery_provider import DiscoveryProvider
        from agent_platform.tools.skill_provider import SkillProvider

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "translate", "Translate text", "Translate: {{text}}")

        kb = KnowledgeStore(persist_dir=str(tmp_path / "kb_index"))
        _write_doc(tmp_path, "doc.md", "# Translation\n\nTranslation guide.")
        kb.ingest(tmp_path / "doc.md")

        provider = DiscoveryProvider(
            skill_provider=SkillProvider(
                skills_dir=str(skills_dir), llm_provider=AsyncMock(),
            ),
            knowledge_store=kb,
        )

        result = await provider.call_tool(
            "discover",
            {"query": "translate", "sources": json.dumps(["skills"])},
        )
        assert result.success
        data = json.loads(result.output)
        for r in data:
            assert r["type"] == "skill"

    @pytest.mark.asyncio
    async def test_st_v4_3_3_empty_results(self, tmp_path):
        """ST-V4-3.3: discover with no results."""
        from agent_platform.tools.discovery_provider import DiscoveryProvider

        provider = DiscoveryProvider()
        result = await provider.call_tool(
            "discover", {"query": "something completely unrelated xyz"},
        )
        assert result.success
        data = json.loads(result.output)
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_st_v4_3_4_result_format(self, tmp_path):
        """ST-V4-3.4: discover result format."""
        from agent_platform.tools.discovery_provider import DiscoveryProvider
        from agent_platform.tools.skill_provider import SkillProvider

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "greet", "Generate greeting", "Hello {{text}}")

        provider = DiscoveryProvider(
            skill_provider=SkillProvider(
                skills_dir=str(skills_dir), llm_provider=AsyncMock(),
            ),
        )

        result = await provider.call_tool("discover", {"query": "greeting"})
        data = json.loads(result.output)

        valid_types = {"skill", "template", "mcp_server", "knowledge", "memory"}
        for r in data:
            assert r["type"] in valid_types
            assert isinstance(r["name"], str) and r["name"]
            assert isinstance(r["score"], (int, float))
            assert 0 <= r["score"] <= 1.0001  # small float tolerance

    @pytest.mark.asyncio
    async def test_st_v4_3_5_analyze_uses_discover(self, tmp_path):
        """ST-V4-3.5: analyze_capabilities uses discover."""
        from agent_platform.tools.capability_tools import CapabilityToolProvider
        from agent_platform.tools.discovery_provider import DiscoveryProvider
        from agent_platform.tools.skill_provider import SkillProvider

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "review", "Review code", "Review: {{text}}")

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Assessment done.", usage={},
        )

        skill_provider = SkillProvider(
            skills_dir=str(skills_dir), llm_provider=mock_llm,
        )
        discovery = DiscoveryProvider(skill_provider=skill_provider)

        provider = CapabilityToolProvider(
            llm_provider=mock_llm,
            discovery_provider=discovery,
        )

        result = await provider.call_tool(
            "analyze_capabilities", {"task": "review code quality"},
        )
        assert result.success
        data = json.loads(result.output)
        assert "discovered" in data
        assert "assessment" in data

    @pytest.mark.asyncio
    async def test_st_v4_3_6_app_integration(self, tmp_path):
        """ST-V4-3.6: discover registered in create_app."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "default.md").write_text("You are a helpful assistant.")
        (tmp_path / "skills").mkdir()
        (tmp_path / "knowledge").mkdir()

        (tmp_path / "lyra.config.json").write_text(json.dumps({
            "dataDir": str(tmp_path / "data"),
            "systemPromptsDir": str(prompts_dir),
            "skillsDir": str(tmp_path / "skills"),
            "knowledgeDir": str(tmp_path / "knowledge"),
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
                assert "discover" in names
