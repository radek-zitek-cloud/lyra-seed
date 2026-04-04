"""
Smoke tests for V1 Phase 3 — Tool System.

Each test function maps to a smoke test ID from SMOKE_TESTS.md.
All LLM calls are mocked — no real API calls.
"""

from unittest.mock import AsyncMock

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v1-phase-3"),
]


class TestV1Phase3:
    """ST-3.x: Tool System smoke tests."""

    def test_st_3_1_tool_models_and_protocol(self):
        """ST-3.1: Tool models and ToolProvider protocol."""
        from agent_platform.tools.models import (
            Tool,
            ToolResult,
            ToolType,
        )
        from agent_platform.tools.provider import ToolProvider

        # ToolType enum
        assert ToolType.MCP is not None
        assert ToolType.INTERNAL is not None

        # Tool model
        tool = Tool(
            name="search",
            description="Search the web",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            tool_type=ToolType.MCP,
            source="http://localhost:3001",
        )
        assert tool.name == "search"
        assert tool.tool_type == ToolType.MCP

        # ToolResult model
        result = ToolResult(
            success=True,
            output="Found 3 results",
            duration_ms=150,
        )
        assert result.success is True
        assert result.error is None

        # ToolProvider protocol shape
        assert hasattr(ToolProvider, "list_tools")
        assert hasattr(ToolProvider, "call_tool")

    @pytest.mark.asyncio
    async def test_st_3_2_tool_registry(self):
        """ST-3.2: ToolRegistry aggregates providers."""
        from agent_platform.tools.models import (
            Tool,
            ToolResult,
            ToolType,
        )
        from agent_platform.tools.registry import ToolRegistry

        # Create two mock providers
        provider_a = AsyncMock()
        provider_a.list_tools.return_value = [
            Tool(
                name="search",
                description="Search things",
                input_schema={"type": "object", "properties": {}},
                tool_type=ToolType.MCP,
                source="server-a",
            ),
        ]
        provider_a.call_tool.return_value = ToolResult(
            success=True, output="search result", duration_ms=100
        )

        provider_b = AsyncMock()
        provider_b.list_tools.return_value = [
            Tool(
                name="calculate",
                description="Do math",
                input_schema={
                    "type": "object",
                    "properties": {"expr": {"type": "string"}},
                },
                tool_type=ToolType.INTERNAL,
                source="macro-1",
            ),
        ]
        provider_b.call_tool.return_value = ToolResult(
            success=True, output="42", duration_ms=50
        )

        registry = ToolRegistry()
        registry.register_provider(provider_a)
        registry.register_provider(provider_b)

        # Combined tool list
        tools = await registry.list_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"search", "calculate"}

        # Route to correct provider
        result = await registry.call_tool("search", {"q": "test"})
        assert result.success is True
        assert result.output == "search result"
        provider_a.call_tool.assert_called_once_with("search", {"q": "test"})

        result = await registry.call_tool("calculate", {"expr": "1+1"})
        assert result.output == "42"

        # Unknown tool
        result = await registry.call_tool("nonexistent", {})
        assert result.success is False
        assert result.error is not None

        # JSON Schema for LLM
        schema = await registry.get_tools_schema()
        assert len(schema) == 2
        assert schema[0]["type"] == "function"
        assert "function" in schema[0]

    @pytest.mark.asyncio
    async def test_st_3_3_skill_provider(self, tmp_path):
        """ST-3.3: SkillProvider loads and executes skills."""
        from agent_platform.llm.models import LLMResponse
        from agent_platform.tools.skill_provider import (
            SkillProvider,
        )

        # Write a skill file
        skill_file = tmp_path / "summarize.md"
        skill_file.write_text(
            "---\nname: summarize\n"
            "description: Summarize text\n"
            "parameters:\n"
            "  text:\n"
            "    type: string\n"
            "---\n\n"
            "Please summarize the following:\n\n{{text}}"
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="This is a summary.",
            usage={"prompt_tokens": 20, "completion_tokens": 5},
        )

        provider = SkillProvider(
            skills_dir=str(tmp_path),
            llm_provider=mock_llm,
        )

        # List tools — skill + create_skill
        tools = await provider.list_tools()
        skill_names = [t.name for t in tools if t.name != "create_skill"]
        assert "summarize" in skill_names

        # Call skill
        result = await provider.call_tool(
            "summarize",
            {"text": "Long article here..."},
        )
        assert result.success is True
        assert "summary" in result.output.lower()
        mock_llm.complete.assert_called_once()

        # Verify template was expanded
        call_args = mock_llm.complete.call_args
        messages = call_args[0][0]
        assert "Long article here..." in messages[-1].content

    @pytest.mark.asyncio
    async def test_st_3_4_skill_file_format(self, tmp_path):
        """ST-3.4: Skill file parsing with YAML frontmatter."""
        from agent_platform.tools.skill_provider import (
            parse_skill_file,
        )

        skill_file = tmp_path / "translate.md"
        skill_file.write_text(
            "---\n"
            "name: translate\n"
            "description: Translate text\n"
            "parameters:\n"
            "  lang:\n"
            "    type: string\n"
            "    required: true\n"
            "  text:\n"
            "    type: string\n"
            "    required: true\n"
            "---\n\n"
            "Translate to {{lang}}: {{text}}"
        )

        skill = parse_skill_file(skill_file)
        assert skill.name == "translate"
        assert skill.description == "Translate text"
        assert "lang" in skill.parameters
        assert "text" in skill.parameters
        assert "{{lang}}" in skill.template
        assert "{{text}}" in skill.template

    @pytest.mark.asyncio
    async def test_st_3_5_skills_api(self, tmp_path):
        """ST-3.5: Skills API (read-only)."""
        import httpx as httpx_mod

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        # Create skills + prompts dirs
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "greet.md").write_text(
            "---\nname: greet\n"
            "description: Generate a greeting\n"
            "parameters:\n"
            "  name:\n    type: string\n"
            "---\n\nSay hello to {{name}}"
        )
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "default.md").write_text("You are a helpful assistant.")
        (tmp_path / "lyra.config.json").write_text(
            '{"dataDir": "'
            + str(tmp_path / "data")
            + '", "systemPromptsDir": "'
            + str(prompts_dir)
            + '", "skillsDir": "'
            + str(skills_dir)
            + '", "defaultModel": "test"}'
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
            transport = httpx_mod.ASGITransport(app=app)
            async with httpx_mod.AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                # GET /skills
                resp = await client.get("/skills")
                assert resp.status_code == 200
                skills = resp.json()
                names = [s["name"] for s in skills]
                assert "greet" in names

                # GET /skills/{name}
                resp = await client.get("/skills/greet")
                assert resp.status_code == 200
                assert resp.json()["name"] == "greet"

                # GET /skills/{unknown} → 404
                resp = await client.get("/skills/nonexistent")
                assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_st_3_6_mcp_client_provider(self):
        """ST-3.6: MCPClientProvider implements ToolProvider interface."""
        from agent_platform.tools.mcp_client import MCPClientProvider

        provider = MCPClientProvider()

        # Implements ToolProvider protocol
        assert hasattr(provider, "list_tools")
        assert hasattr(provider, "call_tool")

        # Empty provider returns no tools
        tools = await provider.list_tools()
        assert tools == []

        # Unknown tool fails gracefully
        result = await provider.call_tool("nonexistent", {})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_st_3_7_runtime_uses_tool_registry(self, tmp_path):
        """ST-3.7: Agent runtime uses ToolRegistry."""
        from agent_platform.core.models import Agent, AgentConfig
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.llm.models import LLMResponse, ToolCall
        from agent_platform.observation.events import EventFilter, EventType
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.models import Tool, ToolResult, ToolType
        from agent_platform.tools.registry import ToolRegistry

        db_path = str(tmp_path / "events.db")
        event_bus = InProcessEventBus(db_path=db_path)
        await event_bus.initialize()

        agent_repo = SqliteAgentRepo(str(tmp_path / "agents.db"))
        await agent_repo.initialize()
        conv_repo = SqliteConversationRepo(str(tmp_path / "convos.db"))
        await conv_repo.initialize()

        # Set up a tool provider with a real tool
        mock_provider = AsyncMock()
        mock_provider.list_tools.return_value = [
            Tool(
                name="lookup",
                description="Look up info",
                input_schema={
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                },
                tool_type=ToolType.MCP,
                source="test",
            ),
        ]
        mock_provider.call_tool.return_value = ToolResult(
            success=True,
            output="Found: Python is a programming language.",
            duration_ms=50,
        )

        registry = ToolRegistry()
        registry.register_provider(mock_provider)

        config = AgentConfig(model="test/model")
        agent = Agent(name="tool-agent", config=config)
        await agent_repo.create(agent)

        # LLM first returns tool call, then text
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="tc-1",
                        name="lookup",
                        arguments={"topic": "Python"},
                    )
                ],
                usage={},
            ),
            LLMResponse(
                content="Python is a programming language.",
                usage={},
            ),
        ]

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=registry,
        )

        response = await runtime.run(agent.id, "Tell me about Python")

        assert response.content == "Python is a programming language."

        # Verify tool was called through registry
        call_args = mock_provider.call_tool.call_args
        assert call_args[0][0] == "lookup"
        assert call_args[0][1]["topic"] == "Python"

        # Verify LLM received tool list
        first_call = mock_llm.complete.call_args_list[0]
        assert first_call.kwargs.get("tools") is not None
        assert len(first_call.kwargs["tools"]) == 1

        # Check events include real tool output
        events = await event_bus.query(EventFilter(agent_id=agent.id))
        tool_results = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(tool_results) >= 1
        assert "Python is a programming language" in str(tool_results[0].payload)

        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()
