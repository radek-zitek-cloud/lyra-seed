"""
Smoke tests for V3 Phase 2 — Tool Creation: MCP Servers.

All MCP server connections are mocked — no real subprocesses spawned.
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.phase("v3-phase-2"),
]


class FakeEmbedding:
    """Mock embedding provider."""

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


def _write_server_config(d, name, **overrides):
    cfg = {
        "name": name,
        "description": f"{name} server",
        "command": "echo",
        "args": ["test"],
        "env": {},
        "managed": True,
        "deployed": True,
        **overrides,
    }
    (d / f"{name}.json").write_text(json.dumps(cfg))
    return cfg


class TestV3Phase2:
    """ST-V3-2.x: MCP Server Management smoke tests."""

    def test_st_v3_2_1_manager_loads_configs(self, tmp_path):
        """ST-V3-2.1: MCPServerManager loads configs from directory."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        _write_server_config(tmp_path, "server-a")
        _write_server_config(tmp_path, "server-b", deployed=False)
        # Non-JSON file should be skipped
        (tmp_path / "readme.txt").write_text("ignore me")

        mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))

        configs = mgr.get_configs()
        assert len(configs) == 2
        assert "server-a" in configs
        assert "server-b" in configs
        assert configs["server-a"]["deployed"] is True
        assert configs["server-b"]["deployed"] is False

    @pytest.mark.asyncio
    async def test_st_v3_2_2_add_mcp_server(self, tmp_path):
        """ST-V3-2.2: add_mcp_server writes config."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))

        result = await mgr.call_tool("add_mcp_server", {
            "name": "firecrawl",
            "description": "Web scraping via Firecrawl",
            "command": "npx",
            "args": json.dumps(["-y", "firecrawl-mcp"]),
            "env": json.dumps({"FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"}),
        })
        assert result.success

        # Config file written
        cfg_path = tmp_path / "firecrawl.json"
        assert cfg_path.exists()
        cfg = json.loads(cfg_path.read_text())
        assert cfg["managed"] is True
        assert cfg["deployed"] is True

        # Name validation
        result = await mgr.call_tool("add_mcp_server", {
            "name": "bad name!",
            "command": "echo",
        })
        assert not result.success

        # Duplicate rejected
        result = await mgr.call_tool("add_mcp_server", {
            "name": "firecrawl",
            "command": "echo",
        })
        assert not result.success

    @pytest.mark.asyncio
    async def test_st_v3_2_3_create_mcp_server_scaffold(self, tmp_path):
        """ST-V3-2.3: create_mcp_server scaffolds directory."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))

        result = await mgr.call_tool("create_mcp_server", {
            "name": "microblog-api",
            "description": "CRUD for microblog platform",
        })
        assert result.success

        data = json.loads(result.output)
        assert "path" in data

        # Directory created
        assert (tmp_path / "microblog-api").is_dir()

        # Config written with deployed=false
        cfg = json.loads((tmp_path / "microblog-api.json").read_text())
        assert cfg["deployed"] is False
        assert cfg["managed"] is True

    @pytest.mark.asyncio
    async def test_st_v3_2_4_deploy_requires_hitl(self, tmp_path):
        """ST-V3-2.4: deploy_mcp_server requires HITL."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        _write_server_config(tmp_path, "custom-srv", deployed=False)

        mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))

        result = await mgr.call_tool("deploy_mcp_server", {
            "name": "custom-srv",
        })

        # Should indicate HITL required
        assert result.success
        data = json.loads(result.output)
        assert data.get("requires_hitl") is True
        assert "description" in data

        # Config still not deployed
        cfg = json.loads((tmp_path / "custom-srv.json").read_text())
        assert cfg["deployed"] is False

        # Simulate approval
        result2 = await mgr.call_tool("deploy_mcp_server", {
            "name": "custom-srv",
            "approved": "true",
        })
        assert result2.success

        # Config updated
        cfg2 = json.loads((tmp_path / "custom-srv.json").read_text())
        assert cfg2["deployed"] is True

    @pytest.mark.asyncio
    async def test_st_v3_2_5_list_mcp_servers(self, tmp_path):
        """ST-V3-2.5: list_mcp_servers returns managed servers."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        _write_server_config(tmp_path, "srv-a", description="Alpha server")
        _write_server_config(tmp_path, "srv-b", description="Beta server", deployed=False)

        mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))

        result = await mgr.call_tool("list_mcp_servers", {})
        assert result.success
        data = json.loads(result.output)
        assert len(data) == 2
        names = [s["name"] for s in data]
        assert "srv-a" in names
        assert "srv-b" in names
        # Check status fields
        for s in data:
            assert "deployed" in s
            assert "managed" in s

    @pytest.mark.asyncio
    async def test_st_v3_2_6_semantic_search(self, tmp_path):
        """ST-V3-2.6: list_mcp_servers semantic search."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        _write_server_config(tmp_path, "web-scraper", description="Scrape web pages")
        _write_server_config(tmp_path, "database", description="Query SQL databases")

        embeddings = FakeEmbedding({
            "Scrape web pages": [1.0, 0.0, 0.0],
            "Query SQL databases": [0.0, 1.0, 0.0],
            "crawl websites": [0.95, 0.05, 0.0],
        })

        mgr = MCPServerManager(
            mcp_servers_dir=str(tmp_path),
            embedding_provider=embeddings,
        )

        result = await mgr.call_tool("list_mcp_servers", {
            "query": "crawl websites",
        })
        assert result.success
        data = json.loads(result.output)
        assert data[0]["name"] == "web-scraper"

    @pytest.mark.asyncio
    async def test_st_v3_2_7_stop_mcp_server(self, tmp_path):
        """ST-V3-2.7: stop_mcp_server stops managed server."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        _write_server_config(tmp_path, "stoppable")

        mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))

        result = await mgr.call_tool("stop_mcp_server", {
            "name": "stoppable",
        })
        assert result.success

        # Cannot stop non-managed (platform) server
        result = await mgr.call_tool("stop_mcp_server", {
            "name": "filesystem",
        })
        assert not result.success

    @pytest.mark.asyncio
    async def test_st_v3_2_8_config_editor_lists_section(self, tmp_path):
        """ST-V3-2.8: Config editor lists mcp-servers section."""
        import httpx

        from agent_platform.api.main import create_app
        from agent_platform.core.config import Settings

        mcp_dir = tmp_path / "mcp-servers"
        mcp_dir.mkdir()
        _write_server_config(mcp_dir, "test-srv")

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "default.md").write_text("You are a helpful assistant.")

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        (tmp_path / "lyra.config.json").write_text(json.dumps({
            "dataDir": str(tmp_path / "data"),
            "systemPromptsDir": str(prompts_dir),
            "skillsDir": str(skills_dir),
            "mcpServersDir": str(mcp_dir),
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
                resp = await client.get("/config/files")
                assert resp.status_code == 200
                data = resp.json()
                assert "mcp_servers" in data
                names = [f["name"] for f in data["mcp_servers"]]
                assert "test-srv.json" in names

    @pytest.mark.asyncio
    async def test_st_v3_2_9_reload_detects_new(self, tmp_path):
        """ST-V3-2.9: Reload reconnects new servers."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))
        assert len(mgr.get_configs()) == 0

        # Add config after init
        _write_server_config(tmp_path, "new-srv")
        mgr.reload()

        assert len(mgr.get_configs()) == 1
        assert "new-srv" in mgr.get_configs()

    @pytest.mark.asyncio
    async def test_st_v3_2_10_env_var_resolution(self, tmp_path):
        """ST-V3-2.10: Config env vars resolve ${VAR}."""
        from agent_platform.tools.mcp_server_manager import MCPServerManager

        _write_server_config(
            tmp_path, "env-test",
            env={"API_KEY": "${TEST_SECRET_KEY}"},
        )

        os.environ["TEST_SECRET_KEY"] = "resolved-value"
        try:
            mgr = MCPServerManager(mcp_servers_dir=str(tmp_path))
            configs = mgr.get_configs()
            resolved = mgr.resolve_env(configs["env-test"]["env"])
            assert resolved["API_KEY"] == "resolved-value"
        finally:
            del os.environ["TEST_SECRET_KEY"]
