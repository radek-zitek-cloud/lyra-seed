"""MCP Server Manager — agent-managed MCP server lifecycle.

Manages MCP servers configured in the mcp-servers/ directory.
Supports adding pre-built servers, scaffolding custom ones,
deploying with HITL gates, and hot-reload.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from agent_platform.core.utils import cosine_similarity
from agent_platform.tools.mcp_client import MCPStdioClient
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class MCPServerManager:
    """Manages agent-created MCP server configs and lifecycle."""

    def __init__(
        self,
        mcp_servers_dir: str,
        embedding_provider: Any | None = None,
        mcp_provider: Any | None = None,
    ) -> None:
        self._dir = mcp_servers_dir
        self._embedder = embedding_provider
        self._mcp_provider = mcp_provider
        self._configs: dict[str, dict[str, Any]] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._connected: dict[str, MCPStdioClient] = {}
        self._load_configs()

    def _load_configs(self) -> None:
        self._configs.clear()
        self._embeddings.clear()
        d = Path(self._dir)
        if not d.exists():
            return
        for p in sorted(d.glob("*.json")):
            try:
                cfg = json.loads(p.read_text(encoding="utf-8"))
                name = cfg.get("name", p.stem)
                self._configs[name] = cfg
            except Exception:
                logger.exception("Failed to parse: %s", p)

    def reload(self) -> None:
        self._load_configs()

    async def connect_deployed(self) -> list[str]:
        """Connect all deployed agent-managed servers.

        Returns list of newly connected server names.
        """
        connected: list[str] = []
        for name, cfg in self._configs.items():
            if not cfg.get("deployed"):
                continue
            if name in self._connected:
                continue

            resolved_env = self.resolve_env(cfg.get("env", {}))
            workdir = cfg.get("workdir")

            client = MCPStdioClient(
                server_name=name,
                command=cfg.get("command", "python"),
                args=cfg.get("args", []),
                env=resolved_env,
                cwd=workdir,
            )

            try:
                await client.connect()
                self._connected[name] = client
                # Register tools with the MCP provider
                if self._mcp_provider:
                    for tool in await client.list_tools():
                        self._mcp_provider._tool_map[tool.name] = client
                    if client not in self._mcp_provider._clients:
                        self._mcp_provider._clients.append(client)
                connected.append(name)
                logger.info("Connected agent-managed MCP server: %s", name)
            except Exception:
                logger.exception(
                    "Failed to connect agent-managed MCP server: %s",
                    name,
                )

        return connected

    async def disconnect_server(self, name: str) -> None:
        """Disconnect a running agent-managed server."""
        client = self._connected.pop(name, None)
        if client:
            # Remove tools from provider
            if self._mcp_provider:
                for tool in await client.list_tools():
                    self._mcp_provider._tool_map.pop(tool.name, None)
                if client in self._mcp_provider._clients:
                    self._mcp_provider._clients.remove(client)
            await client.close()
            logger.info("Disconnected agent-managed MCP server: %s", name)

    async def disconnect_all(self) -> None:
        """Disconnect all agent-managed servers."""
        for name in list(self._connected):
            await self.disconnect_server(name)

    def get_configs(self) -> dict[str, dict[str, Any]]:
        return dict(self._configs)

    @staticmethod
    def resolve_env(env: dict[str, str]) -> dict[str, str]:
        from agent_platform.core.utils import resolve_env_vars

        return resolve_env_vars(env)

    async def _ensure_embeddings(self) -> None:
        if not self._embedder:
            return
        missing = [
            n
            for n in self._configs
            if n not in self._embeddings and self._configs[n].get("description")
        ]
        if not missing:
            return
        descs = [self._configs[n]["description"] for n in missing]
        try:
            vecs = await self._embedder.embed(descs)
            for name, vec in zip(missing, vecs):
                self._embeddings[name] = vec
        except Exception:
            logger.exception("Failed to embed server descriptions")

    # ── Tool registration ─────────────────────────────

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="add_mcp_server",
                description="Add a pre-built MCP server package.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "command": {"type": "string"},
                        "args": {
                            "type": "string",
                            "description": "JSON array of args",
                        },
                        "env": {
                            "type": "string",
                            "description": "JSON env vars",
                        },
                    },
                    "required": ["name", "command"],
                },
                tool_type=ToolType.INTERNAL,
                source="mcp_manager",
            ),
            Tool(
                name="create_mcp_server",
                description=(
                    "Scaffold a custom MCP server directory. "
                    "Write code, then deploy_mcp_server."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "command": {
                            "type": "string",
                            "description": "Start command",
                        },
                        "args": {
                            "type": "string",
                            "description": "JSON args",
                        },
                    },
                    "required": ["name"],
                },
                tool_type=ToolType.INTERNAL,
                source="mcp_manager",
            ),
            Tool(
                name="deploy_mcp_server",
                description=(
                    "Request deployment of a scaffolded MCP server. "
                    "Returns server details for human review. "
                    "The human must approve via the API before "
                    "the server is actually deployed."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
                tool_type=ToolType.INTERNAL,
                source="mcp_manager",
            ),
            Tool(
                name="list_mcp_servers",
                description="List MCP servers. Use query for search.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
                tool_type=ToolType.INTERNAL,
                source="mcp_manager",
            ),
            Tool(
                name="stop_mcp_server",
                description="Stop an agent-managed MCP server.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
                tool_type=ToolType.INTERNAL,
                source="mcp_manager",
            ),
        ]

    # ── Tool dispatch ─────────────────────────────────

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        handlers = {
            "add_mcp_server": self._add_server,
            "create_mcp_server": self._create_server,
            "deploy_mcp_server": self._deploy_server,
            "list_mcp_servers": self._list_servers,
            "stop_mcp_server": self._stop_server,
        }
        handler = handlers.get(name)
        if not handler:
            return ToolResult(success=False, error=f"Unknown: {name}")
        return await handler(arguments)

    # ── add_mcp_server ────────────────────────────────

    async def _add_server(self, args: dict[str, Any]) -> ToolResult:
        name = args.get("name", "")
        if not name or not _NAME_RE.match(name):
            return ToolResult(
                success=False,
                error=f"Invalid server name '{name}'.",
            )
        if name in self._configs:
            return ToolResult(
                success=False,
                error=f"Server '{name}' already exists.",
            )

        command = args.get("command", "")
        if not command:
            return ToolResult(
                success=False,
                error="Command is required.",
            )

        raw_args = args.get("args", "[]")
        if isinstance(raw_args, str):
            try:
                parsed_args = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed_args = []
        else:
            parsed_args = raw_args

        raw_env = args.get("env", "{}")
        if isinstance(raw_env, str):
            try:
                parsed_env = json.loads(raw_env)
            except json.JSONDecodeError:
                parsed_env = {}
        else:
            parsed_env = raw_env

        cfg = {
            "name": name,
            "description": args.get("description", ""),
            "command": command,
            "args": parsed_args,
            "env": parsed_env,
            "managed": True,
            "deployed": True,
        }

        self._write_config(name, cfg)
        self._configs[name] = cfg

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "name": name,
                    "status": "added",
                    "deployed": True,
                    "config_file": str(Path(self._dir) / f"{name}.json"),
                }
            ),
        )

    # ── create_mcp_server ─────────────────────────────

    async def _create_server(self, args: dict[str, Any]) -> ToolResult:
        name = args.get("name", "")
        if not name or not _NAME_RE.match(name):
            return ToolResult(
                success=False,
                error=f"Invalid server name '{name}'.",
            )
        if name in self._configs:
            return ToolResult(
                success=False,
                error=f"Server '{name}' already exists.",
            )

        # Create project directory
        project_dir = Path(self._dir) / name
        project_dir.mkdir(parents=True, exist_ok=True)

        cfg = {
            "name": name,
            "description": args.get("description", ""),
            "command": args.get("command", "python"),
            "args": json.loads(args.get("args", '["server.py"]'))
            if isinstance(args.get("args"), str)
            else args.get("args", ["server.py"]),
            "workdir": str(project_dir),
            "env": {},
            "managed": True,
            "deployed": False,
        }

        self._write_config(name, cfg)
        self._configs[name] = cfg

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "name": name,
                    "path": str(project_dir),
                    "config_file": str(Path(self._dir) / f"{name}.json"),
                    "status": "scaffolded",
                    "next_step": (
                        "Write MCP server code in the directory, "
                        "then call deploy_mcp_server."
                    ),
                }
            ),
        )

    # ── deploy_mcp_server ─────────────────────────────

    async def _deploy_server(self, args: dict[str, Any]) -> ToolResult:
        """Request deployment — always returns pending.

        Actual deployment is done by the human via
        approve_deploy(name) or POST /mcp-servers/{name}/deploy.
        """
        name = args.get("name", "")
        cfg = self._configs.get(name)

        if not cfg:
            return ToolResult(
                success=False,
                error=f"Server '{name}' not found.",
            )

        if not cfg.get("managed"):
            return ToolResult(
                success=False,
                error="Cannot deploy platform-managed servers.",
            )

        if cfg.get("deployed"):
            return ToolResult(
                success=True,
                output=json.dumps(
                    {
                        "name": name,
                        "status": "already_deployed",
                    }
                ),
            )

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "requires_approval": True,
                    "name": name,
                    "description": cfg.get("description", ""),
                    "command": cfg.get("command", ""),
                    "args": cfg.get("args", []),
                    "workdir": cfg.get("workdir", ""),
                    "message": (
                        "Deployment request submitted. "
                        "The human must approve via "
                        "POST /mcp-servers/{name}/deploy "
                        "or the config editor before "
                        "the server will start."
                    ),
                }
            ),
        )

    def approve_deploy(self, name: str) -> bool:
        """Approve deployment — called by human via API only."""
        cfg = self._configs.get(name)
        if not cfg or not cfg.get("managed"):
            return False
        cfg["deployed"] = True
        self._write_config(name, cfg)
        self._configs[name] = cfg
        return True

    # ── list_mcp_servers ──────────────────────────────

    async def _list_servers(self, args: dict[str, Any]) -> ToolResult:
        if not self._configs:
            return ToolResult(
                success=True,
                output="No agent-managed MCP servers.",
            )

        query = args.get("query")
        servers = list(self._configs.values())

        if query and self._embedder:
            await self._ensure_embeddings()
            try:
                vecs = await self._embedder.embed([query])
                query_vec = vecs[0]
                scored = []
                for s in servers:
                    vec = self._embeddings.get(s["name"])
                    if vec:
                        sim = cosine_similarity(query_vec, vec)
                        scored.append((sim, s))
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    servers = [s for _, s in scored]
            except Exception:
                logger.exception("Server search failed")

        info = [
            {
                "name": s["name"],
                "description": s.get("description", ""),
                "deployed": s.get("deployed", False),
                "managed": s.get("managed", True),
                "command": s.get("command", ""),
            }
            for s in servers
        ]
        return ToolResult(
            success=True,
            output=json.dumps(info, indent=2),
        )

    # ── stop_mcp_server ───────────────────────────────

    async def _stop_server(self, args: dict[str, Any]) -> ToolResult:
        name = args.get("name", "")
        cfg = self._configs.get(name)

        if not cfg:
            return ToolResult(
                success=False,
                error=(f"Server '{name}' not found in agent-managed servers."),
            )

        if not cfg.get("managed"):
            return ToolResult(
                success=False,
                error="Cannot stop platform-managed servers.",
            )

        cfg["deployed"] = False
        self._write_config(name, cfg)
        self._configs[name] = cfg

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "name": name,
                    "status": "stopped",
                }
            ),
        )

    # ── Helpers ────────────────────────────────────────

    def _write_config(self, name: str, cfg: dict) -> None:
        d = Path(self._dir)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{name}.json"
        path.write_text(
            json.dumps(cfg, indent=2),
            encoding="utf-8",
        )
