"""
Smoke tests for V3 Phase 1 — Tool Creation: Skills.

All LLM and embedding calls are mocked.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent_platform.llm.models import LLMResponse

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v3-phase-1"),
]


def _write_skill(skills_dir: Path, name: str, desc: str, template: str) -> Path:
    path = skills_dir / f"{name}.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {desc}\n"
        f"parameters:\n  text:\n    type: string\n---\n\n{template}",
        encoding="utf-8",
    )
    return path


class FakeEmbedding:
    """Mock embedding provider returning deterministic vectors."""

    def __init__(self, vectors: dict[str, list[float]] | None = None):
        self._vectors = vectors or {}
        self._default_dim = 3

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for t in texts:
            if t in self._vectors:
                results.append(self._vectors[t])
            else:
                # Deterministic hash-based vector
                h = hash(t) % 1000
                results.append(
                    [h / 1000, (h * 7 % 1000) / 1000, (h * 13 % 1000) / 1000]
                )
        return results

    async def embed_query(self, text: str) -> list[float]:
        vecs = await self.embed([text])
        return vecs[0]


class TestV3Phase1:
    """ST-V3-1.x: Tool Creation — Skills smoke tests."""

    @pytest.mark.asyncio
    async def test_st_v3_1_1_test_skill_dry_run(self, tmp_path):
        """ST-V3-1.1: test_skill dry-runs and evaluates a template."""
        from agent_platform.tools.skill_provider import SkillProvider

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        mock_llm = provider._llm
        call_count = 0

        async def multi_call(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    content="Here are 3 bullet points about AI.", usage={}
                )
            else:
                return LLMResponse(
                    content=json.dumps(
                        {"verdict": "PASS", "reasoning": "Output matches description."}
                    ),
                    usage={},
                )

        mock_llm.complete = multi_call

        result = await provider.call_tool(
            "test_skill",
            {
                "template": "Summarize into bullet points:\n\n{{text}}",
                "description": "Summarize text into bullet points",
                "test_args": json.dumps({"text": "AI is transforming the world."}),
            },
        )

        assert result.success
        data = json.loads(result.output)
        assert "output" in data
        assert data["verdict"] == "PASS"
        assert "reasoning" in data
        assert call_count == 2

        # No file created
        md_files = list(tmp_path.glob("*.md"))
        assert len(md_files) == 0

    @pytest.mark.asyncio
    async def test_st_v3_1_2_update_skill_versions(self, tmp_path):
        """ST-V3-1.2: update_skill versions an existing skill."""
        from agent_platform.tools.skill_provider import SkillProvider

        _write_skill(tmp_path, "greet", "Greet someone", "Hello {{text}}")

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        result = await provider.call_tool(
            "update_skill",
            {
                "name": "greet",
                "description": "Greet someone warmly",
                "template": "Hey there {{text}}, welcome!",
            },
        )

        assert result.success

        # Version file exists
        assert (tmp_path / "greet.v1.md").exists()
        # Active file updated
        active = (tmp_path / "greet.md").read_text()
        assert "Hey there" in active
        # Version file not loaded
        tools = await provider.list_tools()
        names = [t.name for t in tools]
        assert "greet" in names
        assert "greet.v1" not in names

    @pytest.mark.asyncio
    async def test_st_v3_1_3_update_rejects_nonexistent(self, tmp_path):
        """ST-V3-1.3: update_skill rejects nonexistent skill."""
        from agent_platform.tools.skill_provider import SkillProvider

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        result = await provider.call_tool(
            "update_skill",
            {
                "name": "nonexistent",
                "template": "Does not matter",
            },
        )

        assert not result.success
        assert "create_skill" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_st_v3_1_4_multiple_version_increments(self, tmp_path):
        """ST-V3-1.4: Multiple updates increment version numbers."""
        from agent_platform.tools.skill_provider import SkillProvider

        _write_skill(tmp_path, "counter", "Count things", "Count: {{text}}")

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        for i in range(3):
            result = await provider.call_tool(
                "update_skill",
                {
                    "name": "counter",
                    "template": f"Version {i + 2}: {{{{text}}}}",
                },
            )
            assert result.success

        # Check version files
        assert (tmp_path / "counter.v1.md").exists()
        assert (tmp_path / "counter.v2.md").exists()
        assert (tmp_path / "counter.v3.md").exists()
        # Active has latest
        active = (tmp_path / "counter.md").read_text()
        assert "Version 4" in active
        # Only active loaded
        tools = await provider.list_tools()
        skill_names = [t.name for t in tools if t.name == "counter"]
        assert len(skill_names) == 1

    @pytest.mark.asyncio
    async def test_st_v3_1_5_name_format_validation(self, tmp_path):
        """ST-V3-1.5: create_skill validates name format."""
        from agent_platform.tools.skill_provider import SkillProvider

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        # Valid names
        for name in ["my_skill", "code-review", "summarize2"]:
            result = await provider.call_tool(
                "create_skill",
                {"name": name, "template": f"Do {name}: {{{{text}}}}"},
            )
            assert result.success, f"Should accept '{name}': {result.error}"

        # Invalid names
        for name in ["my skill", "a/b", "hello!", "foo@bar", ""]:
            result = await provider.call_tool(
                "create_skill",
                {"name": name, "template": "Doesn't matter"},
            )
            assert not result.success, f"Should reject '{name}'"

    @pytest.mark.asyncio
    async def test_st_v3_1_6_core_tool_name_rejection(self, tmp_path):
        """ST-V3-1.6: create_skill rejects core tool names."""
        from agent_platform.tools.skill_provider import SkillProvider

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        reserved = [
            "remember",
            "recall",
            "forget",
            "spawn_agent",
            "list_skills",
            "create_skill",
            "test_skill",
            "update_skill",
        ]

        for name in reserved:
            result = await provider.call_tool(
                "create_skill",
                {"name": name, "template": "Doesn't matter"},
            )
            assert not result.success, f"Should reject '{name}'"
            assert "reserved" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_st_v3_1_7_test_skill_uses_agent_model(self, tmp_path):
        """ST-V3-1.7: test_skill uses agent's model."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.tools.skill_provider import SkillProvider

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        await agent_repo.initialize()

        agent = Agent(name="tester", config=AgentConfig(model="my-test-model"))
        await agent_repo.create(agent)

        mock_llm = AsyncMock()
        exec_model = None

        async def capture_model(messages, *a, **kw):
            nonlocal exec_model
            config = kw.get("config")
            if exec_model is None and config:
                exec_model = config.model
            return LLMResponse(
                content=json.dumps({"verdict": "PASS", "reasoning": "ok"}),
                usage={},
            )

        mock_llm.complete = capture_model

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=mock_llm,
            agent_repo=agent_repo,
        )

        await provider.call_tool(
            "test_skill",
            {
                "template": "Test: {{text}}",
                "description": "Test skill",
                "test_args": json.dumps({"text": "hello"}),
                "agent_id": agent.id,
            },
        )

        assert exec_model == "my-test-model"
        await agent_repo.close()

    @pytest.mark.asyncio
    async def test_st_v3_1_8_version_files_excluded(self, tmp_path):
        """ST-V3-1.8: Version files excluded from skill loading."""
        from agent_platform.tools.skill_provider import SkillProvider

        _write_skill(tmp_path, "foo", "Foo skill", "Do foo: {{text}}")
        # Write version files manually
        (tmp_path / "foo.v1.md").write_text(
            "---\nname: foo.v1\ndescription: Old\n---\n\nOld version"
        )
        (tmp_path / "foo.v2.md").write_text(
            "---\nname: foo.v2\ndescription: Older\n---\n\nOlder version"
        )

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        tools = await provider.list_tools()
        skill_names = [
            t.name
            for t in tools
            if t.name
            not in ("list_skills", "create_skill", "test_skill", "update_skill")
        ]
        assert skill_names == ["foo"]

    @pytest.mark.asyncio
    async def test_st_v3_1_9_semantic_search(self, tmp_path):
        """ST-V3-1.9: list_skills semantic search."""
        from agent_platform.tools.skill_provider import SkillProvider

        _write_skill(
            tmp_path,
            "summarize",
            "Summarize text into bullet points",
            "Summarize: {{text}}",
        )
        _write_skill(
            tmp_path,
            "translate",
            "Translate text to another language",
            "Translate: {{text}}",
        )
        _write_skill(
            tmp_path, "review", "Review code for bugs and quality", "Review: {{text}}"
        )

        # Embeddings: make "summarize" description close to query
        embeddings = FakeEmbedding(
            {
                "Summarize text into bullet points": [1.0, 0.0, 0.0],
                "Translate text to another language": [0.0, 1.0, 0.0],
                "Review code for bugs and quality": [0.0, 0.0, 1.0],
                "condense text into key points": [
                    0.95,
                    0.05,
                    0.0,
                ],  # close to summarize
            }
        )

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
            embedding_provider=embeddings,
        )

        result = await provider.call_tool(
            "list_skills",
            {"query": "condense text into key points"},
        )

        assert result.success
        data = json.loads(result.output)
        assert len(data) >= 1
        # Summarize should be first (most similar)
        assert data[0]["name"] == "summarize"

        # Without query — returns all
        result_all = await provider.call_tool("list_skills", {})
        data_all = json.loads(result_all.output)
        assert len(data_all) == 3

    @pytest.mark.asyncio
    async def test_st_v3_1_10_deduplication(self, tmp_path):
        """ST-V3-1.10: create_skill deduplication."""
        from agent_platform.tools.skill_provider import SkillProvider

        _write_skill(
            tmp_path,
            "summarize",
            "Summarize text into bullet points",
            "Summarize: {{text}}",
        )

        # Make new description very similar to existing
        embeddings = FakeEmbedding(
            {
                "Summarize text into bullet points": [1.0, 0.0, 0.0],
                "Condense text into concise bullet points": [
                    0.99,
                    0.01,
                    0.0,
                ],  # very similar
                "Translate text to French": [0.0, 1.0, 0.0],  # different
            }
        )

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
            embedding_provider=embeddings,
        )

        # Should reject — too similar to summarize
        result = await provider.call_tool(
            "create_skill",
            {
                "name": "condense",
                "description": "Condense text into concise bullet points",
                "template": "Condense: {{text}}",
            },
        )
        assert not result.success
        assert "summarize" in (result.error or "").lower()

        # Should allow — different enough
        result2 = await provider.call_tool(
            "create_skill",
            {
                "name": "translate-fr",
                "description": "Translate text to French",
                "template": "Translate to French: {{text}}",
            },
        )
        assert result2.success

    @pytest.mark.asyncio
    async def test_st_v3_1_11_graceful_without_embeddings(self, tmp_path):
        """ST-V3-1.11: Graceful degradation without embedding provider."""
        from agent_platform.tools.skill_provider import SkillProvider

        _write_skill(tmp_path, "greet", "Greet someone", "Hello {{text}}")

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
            # No embedding_provider
        )

        # list_skills without query works
        result = await provider.call_tool("list_skills", {})
        assert result.success

        # list_skills with query returns all (no crash)
        result = await provider.call_tool("list_skills", {"query": "greeting"})
        assert result.success

        # create_skill works (no dedup crash)
        result = await provider.call_tool(
            "create_skill",
            {
                "name": "farewell",
                "description": "Say goodbye",
                "template": "Goodbye {{text}}",
            },
        )
        assert result.success
