"""MCP client — real stdio JSON-RPC transport.

Connects to MCP servers via subprocess stdin/stdout using the
Model Context Protocol JSON-RPC format.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any

from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)


class MCPStdioClient:
    """MCP client that communicates with a server over stdio JSON-RPC."""

    def __init__(
        self,
        server_name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._server_name = server_name
        self._command = command
        self._args = args or []
        self._env = env or {}
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._tools: list[Tool] = []
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Start the MCP server subprocess and initialize."""
        # Merge env with current environment
        proc_env = {**os.environ, **self._env}

        logger.info(
            "Starting MCP server '%s': %s %s",
            self._server_name,
            self._command,
            " ".join(self._args),
        )

        self._process = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=proc_env,
        )

        # Send initialize request
        init_result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "lyra", "version": "0.1.0"},
            },
        )
        logger.info(
            "MCP server '%s' initialized: %s",
            self._server_name,
            init_result.get("serverInfo", {}),
        )

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

        # Discover tools
        tools_result = await self._send_request("tools/list", {})
        raw_tools = tools_result.get("tools", [])
        self._tools = []
        for t in raw_tools:
            self._tools.append(
                Tool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    tool_type=ToolType.MCP,
                    source=self._server_name,
                )
            )
        logger.info(
            "MCP server '%s': discovered %d tools: %s",
            self._server_name,
            len(self._tools),
            [t.name for t in self._tools],
        )

    async def close(self) -> None:
        """Shut down the MCP server subprocess."""
        if self._process and self._process.returncode is None:
            logger.info("Shutting down MCP server '%s'", self._server_name)
            # Close stdin to signal EOF
            if self._process.stdin:
                self._process.stdin.close()
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except TimeoutError:
                logger.warning(
                    "MCP server '%s' didn't stop, killing",
                    self._server_name,
                )
                self._process.kill()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2.0)
                except TimeoutError:
                    pass
        self._process = None

    async def list_tools(self) -> list[Tool]:
        """Return discovered tools."""
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Call a tool on the MCP server."""
        start = time.monotonic()
        try:
            result = await self._send_request(
                "tools/call",
                {
                    "name": name,
                    "arguments": arguments,
                },
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            # MCP returns content array
            content_parts = result.get("content", [])
            output_parts = []
            for part in content_parts:
                if part.get("type") == "text":
                    output_parts.append(part.get("text", ""))
                else:
                    output_parts.append(json.dumps(part))

            output = "\n".join(output_parts)
            is_error = result.get("isError", False)

            return ToolResult(
                success=not is_error,
                output=output,
                error=output if is_error else None,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def _send_request(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response."""
        async with self._lock:
            if not self._process or not self._process.stdin or not self._process.stdout:
                raise RuntimeError(f"MCP server '{self._server_name}' not connected")

            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params,
            }

            line = json.dumps(request) + "\n"
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()

            # Read response — skip notifications, wait for matching id
            while True:
                response_line = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=30.0
                )
                if not response_line:
                    stderr_output = ""
                    if self._process.stderr:
                        try:
                            stderr_data = await asyncio.wait_for(
                                self._process.stderr.read(4096), timeout=1.0
                            )
                            stderr_output = stderr_data.decode(errors="replace")
                        except TimeoutError:
                            pass
                    raise RuntimeError(
                        f"MCP server '{self._server_name}' closed unexpectedly. "
                        f"stderr: {stderr_output}"
                    )

                response = json.loads(response_line.decode())

                # Skip notifications (no id field)
                if "id" not in response:
                    continue

                if response.get("id") != self._request_id:
                    continue

                if "error" in response:
                    err = response["error"]
                    raise RuntimeError(
                        f"MCP error from '{self._server_name}': "
                        f"{err.get('message', err)}"
                    )

                return response.get("result", {})

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        line = json.dumps(notification) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()


class MCPClientProvider:
    """ToolProvider that aggregates tools from multiple MCP stdio clients."""

    def __init__(self) -> None:
        self._clients: list[MCPStdioClient] = []
        self._tool_map: dict[str, MCPStdioClient] = {}

    def add_client(self, client: MCPStdioClient) -> None:
        """Add an MCP client."""
        self._clients.append(client)

    async def connect_all(self) -> None:
        """Connect all MCP clients and discover tools."""
        for client in self._clients:
            try:
                await client.connect()
                for tool in await client.list_tools():
                    self._tool_map[tool.name] = client
            except Exception:
                logger.exception(
                    "Failed to connect MCP client '%s'",
                    client._server_name,
                )

    async def close_all(self) -> None:
        """Close all MCP clients."""
        for client in self._clients:
            try:
                await client.close()
            except Exception:
                logger.exception(
                    "Error closing MCP client '%s'",
                    client._server_name,
                )

    async def list_tools(self) -> list[Tool]:
        """Return all tools from all connected MCP servers."""
        tools: list[Tool] = []
        for client in self._clients:
            tools.extend(await client.list_tools())
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Route a tool call to the correct MCP client."""
        client = self._tool_map.get(name)
        if client is None:
            return ToolResult(success=False, error=f"Unknown MCP tool: {name}")
        return await client.call_tool(name, arguments)
