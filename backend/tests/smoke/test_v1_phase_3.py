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
        assert ToolType.PROMPT_MACRO is not None

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
                tool_type=ToolType.PROMPT_MACRO,
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
    async def test_st_3_3_prompt_macro_provider(self):
        """ST-3.3: PromptMacro model and provider."""
        from agent_platform.llm.models import LLMResponse
        from agent_platform.tools.prompt_macro import (
            PromptMacro,
            PromptMacroProvider,
        )

        macro = PromptMacro(
            name="summarize",
            description="Summarize text",
            template="Please summarize the following:\n\n{{text}}",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="This is a summary.",
            usage={"prompt_tokens": 20, "completion_tokens": 5},
        )

        provider = PromptMacroProvider(llm_provider=mock_llm)
        provider.add_macro(macro)

        # List tools
        tools = await provider.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "summarize"

        # Call tool — should expand template and call LLM
        result = await provider.call_tool("summarize", {"text": "Long article here..."})
        assert result.success is True
        assert "summary" in result.output.lower()
        mock_llm.complete.assert_called_once()

        # Verify template was expanded in the LLM call
        call_args = mock_llm.complete.call_args
        messages = call_args[0][0]  # first positional arg
        assert "Long article here..." in messages[-1].content

        # Verify LLM config is passed through when set
        from agent_platform.llm.models import LLMConfig

        mock_llm.reset_mock()
        mock_llm.complete.return_value = LLMResponse(
            content="Summary with config.",
            usage={"prompt_tokens": 20, "completion_tokens": 5},
        )
        provider._llm_config = LLMConfig(model="test/model", temperature=0.5)
        result = await provider.call_tool("summarize", {"text": "Some text"})
        assert result.success is True
        _, kwargs = mock_llm.complete.call_args
        assert kwargs["config"].model == "test/model"
        assert kwargs["config"].temperature == 0.5

    @pytest.mark.asyncio
    async def test_st_3_4_macro_sqlite_repo(self, tmp_path):
        """ST-3.4: Prompt macro SQLite repository."""
        from agent_platform.db.sqlite_macro_repo import SqliteMacroRepo
        from agent_platform.tools.prompt_macro import PromptMacro

        db_path = str(tmp_path / "test_macros.db")
        repo = SqliteMacroRepo(db_path)
        await repo.initialize()

        macro = PromptMacro(
            name="translate",
            description="Translate text",
            template="Translate to {{lang}}: {{text}}",
            parameters={
                "type": "object",
                "properties": {
                    "lang": {"type": "string"},
                    "text": {"type": "string"},
                },
            },
        )

        # Create
        created = await repo.create(macro)
        assert created.id == macro.id

        # Get
        fetched = await repo.get(macro.id)
        assert fetched is not None
        assert fetched.name == "translate"
        assert "{{lang}}" in fetched.template

        # List
        all_macros = await repo.list()
        assert len(all_macros) == 1

        # Update
        macro.description = "Translate text to any language"
        await repo.update(macro.id, macro)
        fetched = await repo.get(macro.id)
        assert fetched is not None
        assert fetched.description == "Translate text to any language"

        # Delete
        deleted = await repo.delete(macro.id)
        assert deleted is True
        assert await repo.get(macro.id) is None

        await repo.close()

    @pytest.mark.asyncio
    async def test_st_3_5_macro_crud_api(self, tmp_path):
        """ST-3.5: Prompt macro CRUD API."""
        import httpx as httpx_mod

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        settings = Settings(
            openrouter_api_key="sk-test",  # type: ignore[arg-type]
        )
        app = create_app(settings, db_dir=str(tmp_path))

        async with app.router.lifespan_context(app):
            transport = httpx_mod.ASGITransport(app=app)
            async with httpx_mod.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # POST /macros
                resp = await client.post(
                    "/macros",
                    json={
                        "name": "greet",
                        "description": "Generate a greeting",
                        "template": "Say hello to {{name}}",
                        "parameters": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        },
                    },
                )
                assert resp.status_code == 201
                macro_data = resp.json()
                macro_id = macro_data["id"]

                # GET /macros
                resp = await client.get("/macros")
                assert resp.status_code == 200
                macros = resp.json()
                assert len(macros) >= 1

                # GET /macros/{id}
                resp = await client.get(f"/macros/{macro_id}")
                assert resp.status_code == 200
                assert resp.json()["name"] == "greet"

                # PUT /macros/{id}
                resp = await client.put(
                    f"/macros/{macro_id}",
                    json={
                        "name": "greet",
                        "description": "Updated greeting",
                        "template": "Say hello to {{name}}!",
                        "parameters": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        },
                    },
                )
                assert resp.status_code == 200

                # DELETE /macros/{id}
                resp = await client.delete(f"/macros/{macro_id}")
                assert resp.status_code == 200

                # Verify deleted
                resp = await client.get(f"/macros/{macro_id}")
                assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_st_3_6_mcp_tool_provider(self):
        """ST-3.6: MCPToolProvider (stub)."""
        from agent_platform.tools.mcp_provider import MCPToolProvider
        from agent_platform.tools.models import Tool, ToolType

        async def mock_handler(arguments: dict) -> str:
            return f"result for {arguments.get('q', '')}"

        provider = MCPToolProvider(server_name="test-server")
        provider.register_tool(
            Tool(
                name="web_search",
                description="Search the web",
                input_schema={
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                },
                tool_type=ToolType.MCP,
                source="test-server",
            ),
            handler=mock_handler,
        )

        # List tools
        tools = await provider.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "web_search"

        # Call tool
        result = await provider.call_tool("web_search", {"q": "python"})
        assert result.success is True
        assert "python" in result.output

        # Unknown tool
        result = await provider.call_tool("unknown", {})
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
        mock_provider.call_tool.assert_called_once_with("lookup", {"topic": "Python"})

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
