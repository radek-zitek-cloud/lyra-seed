"""
Smoke tests for V2 Phase 7 — Skills (Filesystem-Based Prompt Macros).

All LLM calls are mocked — no real API calls.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent_platform.llm.models import LLMResponse

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v2-phase-7"),
]


def _write_skill(
    skills_dir: Path,
    name: str,
    description: str,
    params: dict,
    template: str,
) -> Path:
    """Write a skill .md file with YAML frontmatter."""
    lines = ["---"]
    lines.append(f"name: {name}")
    lines.append(f"description: {description}")
    if params:
        lines.append("parameters:")
        for pname, pdef in params.items():
            lines.append(f"  {pname}:")
            for k, v in pdef.items():
                lines.append(f"    {k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(template)
    path = skills_dir / f"{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class TestV2Phase7:
    """ST-V2-7.x: Skills smoke tests."""

    def test_st_v2_7_1_skill_file_parsing(self, tmp_path):
        """ST-V2-7.1: Skill file parsing."""
        from agent_platform.tools.skill_provider import (
            parse_skill_file,
        )

        skill_path = _write_skill(
            tmp_path,
            "summarize",
            "Summarize text into bullet points",
            {
                "text": {
                    "type": "string",
                    "description": "Text to summarize",
                    "required": "true",
                }
            },
            "Summarize into 3-5 bullet points:\n\n{{text}}",
        )

        skill = parse_skill_file(skill_path)
        assert skill.name == "summarize"
        assert skill.description == "Summarize text into bullet points"
        assert "text" in skill.parameters
        assert skill.template == "Summarize into 3-5 bullet points:\n\n{{text}}"

    @pytest.mark.asyncio
    async def test_st_v2_7_2_provider_loads_from_directory(
        self,
        tmp_path,
    ):
        """ST-V2-7.2: SkillProvider loads skills from directory."""
        from agent_platform.tools.skill_provider import (
            SkillProvider,
        )

        _write_skill(
            tmp_path,
            "summarize",
            "Summarize text",
            {"text": {"type": "string"}},
            "Summarize:\n{{text}}",
        )
        _write_skill(
            tmp_path,
            "translate",
            "Translate text",
            {"text": {"type": "string"}, "language": {"type": "string"}},
            "Translate to {{language}}:\n{{text}}",
        )

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        tools = await provider.list_tools()
        # 2 skills + list_skills + create_skill
        assert len(tools) == 4
        names = {t.name for t in tools}
        assert "summarize" in names
        assert "translate" in names
        assert "create_skill" in names
        for t in tools:
            assert t.tool_type.value == "prompt_macro"
            assert t.source == "skill"

    @pytest.mark.asyncio
    async def test_st_v2_7_3_provider_executes_skill(
        self,
        tmp_path,
    ):
        """ST-V2-7.3: SkillProvider executes a skill."""
        from agent_platform.tools.skill_provider import (
            SkillProvider,
        )

        _write_skill(
            tmp_path,
            "greet",
            "Generate a greeting",
            {"name": {"type": "string"}},
            "Write a friendly greeting for {{name}}.",
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Hello, World!",
            usage={},
        )

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=mock_llm,
        )

        result = await provider.call_tool(
            "greet",
            {"name": "Radek"},
        )
        assert result.success
        assert result.output == "Hello, World!"

        # Verify template was expanded
        call_args = mock_llm.complete.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "Radek" in prompt
        assert "{{name}}" not in prompt

    @pytest.mark.asyncio
    async def test_st_v2_7_4_create_skill_tool(self, tmp_path):
        """ST-V2-7.4: create_skill writes a new skill file."""
        from agent_platform.tools.skill_provider import (
            SkillProvider,
        )

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=AsyncMock(),
        )

        # Create a new skill
        result = await provider.call_tool(
            "create_skill",
            {
                "name": "my_skill",
                "description": "A custom skill",
                "template": "Do something with {{input}}",
                "parameters": json.dumps(
                    {
                        "input": {
                            "type": "string",
                            "description": "The input",
                        },
                    }
                ),
            },
        )
        assert result.success

        # File should exist
        skill_file = tmp_path / "my_skill.md"
        assert skill_file.exists()

        # Should be immediately available
        tools = await provider.list_tools()
        names = [t.name for t in tools]
        assert "my_skill" in names

        # Duplicate name should be rejected
        result2 = await provider.call_tool(
            "create_skill",
            {
                "name": "my_skill",
                "description": "Duplicate",
                "template": "Duplicate",
            },
        )
        assert not result2.success
        assert "exists" in (result2.error or "").lower()

    @pytest.mark.asyncio
    async def test_st_v2_7_5_skills_api_endpoints(
        self,
        tmp_path,
    ):
        """ST-V2-7.5: Skills API endpoints."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        # Create skills directory with a skill
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(
            skills_dir,
            "test_skill",
            "A test skill",
            {"text": {"type": "string"}},
            "Process: {{text}}",
        )

        # Create prompts dir
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "default.md").write_text(
            "You are a helpful assistant.",
        )

        (tmp_path / "lyra.config.json").write_text(
            json.dumps(
                {
                    "dataDir": str(tmp_path / "data"),
                    "systemPromptsDir": str(prompts_dir),
                    "skillsDir": str(skills_dir),
                    "defaultModel": "test-model",
                }
            ),
        )

        settings = Settings(
            openrouter_api_key="sk-test",
        )
        app = create_app(
            settings,
            db_dir=str(tmp_path / "data"),
            project_root=tmp_path,
        )

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                # GET /skills
                resp = await client.get("/skills")
                assert resp.status_code == 200
                skills = resp.json()
                assert len(skills) >= 1
                names = [s["name"] for s in skills]
                assert "test_skill" in names

                # GET /skills/{name}
                resp = await client.get("/skills/test_skill")
                assert resp.status_code == 200
                skill = resp.json()
                assert skill["name"] == "test_skill"
                assert "template" in skill

                # GET /skills/{unknown} → 404
                resp = await client.get("/skills/nonexistent")
                assert resp.status_code == 404

    def test_st_v2_7_6_old_macro_system_removed(self):
        """ST-V2-7.6: Old macro system removed."""
        # SqliteMacroRepo should not be importable
        with pytest.raises(ImportError):
            from agent_platform.db.sqlite_macro_repo import (  # noqa: F401
                SqliteMacroRepo,
            )

        # macro_routes should not be importable
        with pytest.raises(ImportError):
            from agent_platform.api.macro_routes import (  # noqa: F401
                router,
            )

    def test_st_v2_7_7_platform_config_skills_dir(self):
        """ST-V2-7.7: PlatformConfig has skillsDir field."""
        from agent_platform.core.platform_config import (
            PlatformConfig,
        )

        config = PlatformConfig()
        assert config.skillsDir == "./skills"

        config2 = PlatformConfig(skillsDir="/custom/skills")
        assert config2.skillsDir == "/custom/skills"

    def test_st_v2_7_8_starter_skills_exist(self):
        """ST-V2-7.8: Starter skills exist."""
        from agent_platform.tools.skill_provider import (
            parse_skill_file,
        )

        project_root = Path(__file__).resolve().parent.parent.parent.parent
        skills_dir = project_root / "skills"

        for name in ("summarize", "translate", "code-review"):
            path = skills_dir / f"{name}.md"
            assert path.exists(), f"Missing: {path}"
            skill = parse_skill_file(path)
            assert skill.name == name
            assert skill.description
            assert skill.template

    @pytest.mark.asyncio
    async def test_st_v2_7_9_skill_uses_agent_model(
        self,
        tmp_path,
    ):
        """ST-V2-7.9: Skill execution uses agent's model."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import (
            SqliteAgentRepo,
        )
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import ToolCall
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.registry import ToolRegistry
        from agent_platform.tools.skill_provider import (
            SkillProvider,
        )

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(
            skills_dir,
            "test_skill",
            "Test",
            {"text": {"type": "string"}},
            "Process: {{text}}",
        )

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()

        mock_llm = AsyncMock()
        call_count = 0

        async def track_model(messages, *a, **kw):
            nonlocal call_count
            call_count += 1
            config = kw.get("config")
            if call_count == 1:
                # Agent's main call — returns tool call
                return LLMResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="tc-1",
                            name="test_skill",
                            arguments={"text": "hello"},
                        ),
                    ],
                    usage={},
                )
            elif call_count == 2:
                # Skill execution — check model
                assert config is not None
                assert config.model == "my-special-model"
                return LLMResponse(
                    content="Processed",
                    usage={},
                )
            else:
                return LLMResponse(
                    content="Done",
                    usage={},
                )

        mock_llm.complete = track_model

        provider = SkillProvider(
            skills_dir=str(skills_dir),
            llm_provider=mock_llm,
            agent_repo=agent_repo,
        )

        registry = ToolRegistry()
        registry.register_provider(provider)

        agent = Agent(
            name="model-test",
            config=AgentConfig(model="my-special-model"),
        )
        await agent_repo.create(agent)

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=registry,
        )

        await runtime.run(agent.id, "Use the test_skill")
        assert call_count >= 2

        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_7_10_app_integration(self, tmp_path):
        """ST-V2-7.10: Skills load at startup in create_app."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        # Create skills directory with a skill
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(
            skills_dir,
            "app_skill",
            "Integration test skill",
            {"input": {"type": "string"}},
            "Process: {{input}}",
        )

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "default.md").write_text(
            "You are a helpful assistant.",
        )

        (tmp_path / "lyra.config.json").write_text(
            json.dumps(
                {
                    "dataDir": str(tmp_path / "data"),
                    "systemPromptsDir": str(prompts_dir),
                    "skillsDir": str(skills_dir),
                    "defaultModel": "test-model",
                }
            ),
        )

        settings = Settings(
            openrouter_api_key="sk-test",
        )
        app = create_app(
            settings,
            db_dir=str(tmp_path / "data"),
            project_root=tmp_path,
        )

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                # Skill should appear in tools
                resp = await client.get("/tools")
                assert resp.status_code == 200
                tools = resp.json()
                tool_names = [t["name"] for t in tools]
                assert "app_skill" in tool_names

                # Skill should appear in skills API
                resp = await client.get("/skills")
                assert resp.status_code == 200
                skill_names = [s["name"] for s in resp.json()]
                assert "app_skill" in skill_names

                # /macros should not exist
                resp = await client.get("/macros")
                assert resp.status_code in (404, 405)
