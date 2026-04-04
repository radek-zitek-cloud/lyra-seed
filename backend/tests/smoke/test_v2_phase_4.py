"""
Smoke tests for V2 Phase 4 — Per-Agent Tool Scoping.

All LLM calls are mocked — no real API calls.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent_platform.core.models import Agent, AgentConfig
from agent_platform.llm.models import LLMResponse
from agent_platform.tools.models import Tool, ToolResult, ToolType
from agent_platform.tools.registry import ToolRegistry

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v2-phase-4"),
]


class FakeProvider:
    """Fake tool provider for testing."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = tools

    async def list_tools(self) -> list[Tool]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict) -> ToolResult:
        return ToolResult(success=True, output=f"called {name}")


def _mcp_tool(name: str, source: str) -> Tool:
    return Tool(
        name=name,
        description=f"{name} tool",
        input_schema={"type": "object", "properties": {}},
        tool_type=ToolType.MCP,
        source=source,
    )


def _core_tool(name: str) -> Tool:
    return Tool(
        name=name,
        description=f"{name} tool",
        input_schema={"type": "object", "properties": {}},
        tool_type=ToolType.INTERNAL,
        source="core",
    )


class TestV2Phase4:
    """ST-V2-4.x: Per-Agent Tool Scoping smoke tests."""

    def test_st_v2_4_1_agent_config_allowed_mcp_servers(self):
        """ST-V2-4.1: AgentConfig has allowed_mcp_servers field."""
        config = AgentConfig()
        assert config.allowed_mcp_servers is None

        config2 = AgentConfig(allowed_mcp_servers=["filesystem"])
        assert config2.allowed_mcp_servers == ["filesystem"]

        config3 = AgentConfig(allowed_mcp_servers=[])
        assert config3.allowed_mcp_servers == []

    def test_st_v2_4_2_agent_file_config_allowed_mcp_servers(self):
        """ST-V2-4.2: AgentFileConfig has allowed_mcp_servers."""
        from agent_platform.core.platform_config import (
            AgentFileConfig,
        )

        fc = AgentFileConfig()
        assert fc.allowed_mcp_servers is None

        fc2 = AgentFileConfig.model_validate(
            {"allowed_mcp_servers": ["filesystem", "shell"]}
        )
        assert fc2.allowed_mcp_servers == ["filesystem", "shell"]

    @pytest.mark.asyncio
    async def test_st_v2_4_3_registry_filters_by_mcp_servers(self):
        """ST-V2-4.3: ToolRegistry filters by allowed_mcp_servers."""
        registry = ToolRegistry()

        fs_tools = FakeProvider(
            [
                _mcp_tool("read_file", "filesystem"),
                _mcp_tool("write_file", "filesystem"),
            ]
        )
        shell_tools = FakeProvider(
            [
                _mcp_tool("run_command", "shell"),
            ]
        )
        core = FakeProvider(
            [
                _core_tool("remember"),
                _core_tool("recall"),
            ]
        )

        registry.register_provider(fs_tools)
        registry.register_provider(shell_tools)
        registry.register_provider(core)

        # No filter — all tools
        all_tools = await registry.list_tools()
        assert len(all_tools) == 5

        # Filter to filesystem only
        fs_only = await registry.list_tools(
            allowed_mcp_servers=["filesystem"],
        )
        names = [t.name for t in fs_only]
        assert "read_file" in names
        assert "write_file" in names
        assert "run_command" not in names
        # Core tools always included
        assert "remember" in names
        assert "recall" in names
        assert len(fs_only) == 4

        # Empty list — no MCP tools
        no_mcp = await registry.list_tools(allowed_mcp_servers=[])
        names = [t.name for t in no_mcp]
        assert "read_file" not in names
        assert "run_command" not in names
        assert "remember" in names
        assert len(no_mcp) == 2

        # get_tools_schema respects filter
        schema = await registry.get_tools_schema(
            allowed_mcp_servers=["filesystem"],
        )
        schema_names = [s["function"]["name"] for s in schema]
        assert "read_file" in schema_names
        assert "run_command" not in schema_names

    @pytest.mark.asyncio
    async def test_st_v2_4_4_registry_filters_by_allowed_tools(self):
        """ST-V2-4.4: ToolRegistry filters by allowed_tools."""
        registry = ToolRegistry()
        registry.register_provider(
            FakeProvider(
                [
                    _core_tool("remember"),
                    _core_tool("recall"),
                    _core_tool("forget"),
                    _mcp_tool("read_file", "filesystem"),
                ]
            )
        )

        filtered = await registry.list_tools(
            allowed_tools=["remember", "recall"],
        )
        names = [t.name for t in filtered]
        assert names == ["remember", "recall"]

        schema = await registry.get_tools_schema(
            allowed_tools=["remember"],
        )
        assert len(schema) == 1
        assert schema[0]["function"]["name"] == "remember"

    @pytest.mark.asyncio
    async def test_st_v2_4_5_combined_filtering(self):
        """ST-V2-4.5: Combined MCP server and tool name filtering."""
        registry = ToolRegistry()
        registry.register_provider(
            FakeProvider(
                [
                    _mcp_tool("read_file", "filesystem"),
                    _mcp_tool("write_file", "filesystem"),
                    _mcp_tool("run_command", "shell"),
                    _core_tool("remember"),
                ]
            )
        )

        filtered = await registry.list_tools(
            allowed_mcp_servers=["filesystem"],
            allowed_tools=["read_file", "remember"],
        )
        names = [t.name for t in filtered]
        # read_file passes both filters
        assert "read_file" in names
        # remember passes allowed_tools and is non-MCP
        assert "remember" in names
        # write_file passes MCP filter but not allowed_tools
        assert "write_file" not in names
        # run_command fails MCP filter
        assert "run_command" not in names

    @pytest.mark.asyncio
    async def test_st_v2_4_6_runtime_uses_agent_scope(self, tmp_path):
        """ST-V2-4.6: Runtime uses agent's allowed_mcp_servers."""
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import (
            SqliteAgentRepo,
        )
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()

        registry = ToolRegistry()
        registry.register_provider(
            FakeProvider(
                [
                    _mcp_tool("read_file", "filesystem"),
                    _mcp_tool("run_command", "shell"),
                    _core_tool("remember"),
                ]
            )
        )

        agent = Agent(
            name="scoped",
            config=AgentConfig(
                model="test",
                allowed_mcp_servers=["filesystem"],
            ),
        )
        await agent_repo.create(agent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(content="Done", usage={})

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=registry,
        )

        await runtime.run(agent.id, "Hello")

        # Check what tools were passed to LLM
        call_args = mock_llm.complete.call_args
        tools = call_args.kwargs.get("tools") or (
            call_args[1].get("tools") if len(call_args) > 1 else None
        )
        assert tools is not None
        tool_names = [t["function"]["name"] for t in tools]
        assert "read_file" in tool_names
        assert "remember" in tool_names
        assert "run_command" not in tool_names

        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_4_7_config_resolution_from_file(self, tmp_path):
        """ST-V2-4.7: Agent creation resolves allowed_mcp_servers."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        # Create a prompt config with allowed_mcp_servers
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "scoped-agent.json").write_text(
            json.dumps(
                {
                    "allowed_mcp_servers": ["filesystem"],
                    "temperature": 0.5,
                }
            )
        )
        (prompts_dir / "default.md").write_text("You are a helpful assistant.")

        # Create platform config
        (tmp_path / "lyra.config.json").write_text(
            json.dumps(
                {
                    "dataDir": str(tmp_path / "data"),
                    "systemPromptsDir": str(prompts_dir),
                    "defaultModel": "test-model",
                }
            )
        )

        settings = Settings(
            openrouter_api_key="sk-test",  # type: ignore[arg-type]
        )
        app = create_app(
            settings,
            db_dir=str(tmp_path / "data"),
            project_root=tmp_path,
        )

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/agents",
                    json={"name": "scoped-agent"},
                )
                assert resp.status_code == 201
                data = resp.json()
                assert data["config"]["allowed_mcp_servers"] == ["filesystem"]

    @pytest.mark.asyncio
    async def test_st_v2_4_8_allowed_tools_enforcement(self, tmp_path):
        """ST-V2-4.8: allowed_tools whitelist scopes tool schema."""
        from agent_platform.core.runtime import AgentRuntime
        from agent_platform.db.sqlite_agent_repo import (
            SqliteAgentRepo,
        )
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()

        registry = ToolRegistry()
        registry.register_provider(
            FakeProvider(
                [
                    _core_tool("remember"),
                    _core_tool("recall"),
                    _core_tool("spawn_agent"),
                    _mcp_tool("read_file", "filesystem"),
                ]
            )
        )

        agent = Agent(
            name="restricted",
            config=AgentConfig(
                model="test",
                allowed_tools=["remember", "recall"],
            ),
        )
        await agent_repo.create(agent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(content="Done", usage={})

        runtime = AgentRuntime(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=registry,
        )

        await runtime.run(agent.id, "Hello")

        call_args = mock_llm.complete.call_args
        tools = call_args.kwargs.get("tools") or (
            call_args[1].get("tools") if len(call_args) > 1 else None
        )
        tool_names = [t["function"]["name"] for t in tools]
        assert tool_names == ["remember", "recall"]

        await agent_repo.close()
        await conv_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_4_9_child_inherits_parent_scope(self, tmp_path):
        """ST-V2-4.9: Child inherits parent's tool scope."""
        from agent_platform.db.sqlite_agent_repo import (
            SqliteAgentRepo,
        )
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import (
            SqliteMessageRepo,
        )
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import (
            AgentSpawnerProvider,
        )

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        parent = Agent(
            name="parent",
            config=AgentConfig(
                model="test",
                allowed_mcp_servers=["filesystem"],
            ),
        )
        await agent_repo.create(parent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(content="Done", usage={})

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
        )

        result = await spawner.call_tool(
            "spawn_agent",
            {
                "name": "child",
                "task": "Do work",
                "agent_id": parent.id,
            },
        )
        assert result.success

        data = json.loads(result.output)
        child = await agent_repo.get(data["child_agent_id"])
        assert child is not None
        assert child.config.allowed_mcp_servers == ["filesystem"]

        await asyncio.sleep(0.5)
        await spawner.cancel_all_tasks()
        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    @pytest.mark.asyncio
    async def test_st_v2_4_10_child_template_overrides_scope(self, tmp_path):
        """ST-V2-4.10: Child template overrides parent scope."""
        from agent_platform.core.platform_config import (
            AgentFileConfig,
        )
        from agent_platform.db.sqlite_agent_repo import (
            SqliteAgentRepo,
        )
        from agent_platform.db.sqlite_conversation_repo import (
            SqliteConversationRepo,
        )
        from agent_platform.db.sqlite_message_repo import (
            SqliteMessageRepo,
        )
        from agent_platform.observation.in_process_event_bus import (
            InProcessEventBus,
        )
        from agent_platform.tools.agent_spawner import (
            AgentSpawnerProvider,
        )

        db = str(tmp_path / "test.db")
        agent_repo = SqliteAgentRepo(db)
        conv_repo = SqliteConversationRepo(db)
        msg_repo = SqliteMessageRepo(db)
        event_bus = InProcessEventBus()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await msg_repo.initialize()

        parent = Agent(
            name="parent",
            config=AgentConfig(
                model="test",
                allowed_mcp_servers=["filesystem"],
            ),
        )
        await agent_repo.create(parent)

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(content="Done", usage={})

        def mock_config_resolver(name):
            if name == "full-access":
                return AgentFileConfig(
                    allowed_mcp_servers=["filesystem", "shell"],
                )
            return AgentFileConfig()

        def mock_prompt_resolver(name):
            return "You are a worker."

        spawner = AgentSpawnerProvider(
            agent_repo=agent_repo,
            conversation_repo=conv_repo,
            llm_provider=mock_llm,
            event_bus=event_bus,
            tool_registry=ToolRegistry(),
            message_repo=msg_repo,
            system_prompt_resolver=mock_prompt_resolver,
            agent_config_resolver=mock_config_resolver,
        )

        result = await spawner.call_tool(
            "spawn_agent",
            {
                "name": "child",
                "task": "Do work",
                "template": "full-access",
                "agent_id": parent.id,
            },
        )
        assert result.success

        data = json.loads(result.output)
        child = await agent_repo.get(data["child_agent_id"])
        assert child is not None
        assert child.config.allowed_mcp_servers == [
            "filesystem",
            "shell",
        ]

        await asyncio.sleep(0.5)
        await spawner.cancel_all_tasks()
        await agent_repo.close()
        await conv_repo.close()
        await msg_repo.close()

    def test_st_v2_4_11_configuration_guide_exists(self):
        """ST-V2-4.11: CONFIGURATION_GUIDE.md exists and covers topics."""
        guide_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "docs"
            / "CONFIGURATION_GUIDE.md"
        )
        assert guide_path.exists(), f"CONFIGURATION_GUIDE.md not found at {guide_path}"

        content = guide_path.read_text(encoding="utf-8")
        assert ".env" in content
        assert "lyra.config.json" in content
        assert "prompts/" in content or "agent JSON" in content.lower()
        assert "system prompt" in content.lower()
        assert "resolution" in content.lower()
        assert "allowed_mcp_servers" in content
        assert "allowed_tools" in content
