# Lyra MCP Server Management

## What Are MCP Servers

MCP (Model Context Protocol) servers are external processes that provide tools to agents. They communicate via JSON-RPC over stdio. Each server exposes tools that agents can call — filesystem operations, shell commands, web scraping, API integrations, etc.

## Two Types of MCP Servers

### Platform-Configured

Defined in `lyra.config.json` under `mcpServers`. Managed by the platform administrator. Cannot be stopped or modified by agents.

### Agent-Managed

Defined in `mcp-servers/{name}.json`. Created by agents at runtime. Can be added, deployed, and stopped by agents.

## Platform-Configured Servers

### filesystem (fast-filesystem-mcp)

Provides 25 filesystem tools: read, write, edit, copy, move, delete, search, list, compress, sync, etc. Configured with backup creation and debug logging.

### shell (mcp-shell-server)

Provides shell_execute tool with a whitelist of allowed commands: ls, cat, git, python, npm, curl, etc. Commands not in the whitelist are rejected.

### firecrawl (firecrawl-mcp)

Provides web scraping tools: firecrawl_search (web search), firecrawl_scrape (page content extraction). Requires FIRECRAWL_API_KEY in .env.

## Agent MCP Server Tools

### add_mcp_server

Add a pre-built MCP server from npm or pip. Parameters:
- name: server identifier
- command: executable (npx, uvx, python, etc.)
- args: JSON array of arguments
- description: what the server provides
- env: JSON object of environment variables (supports ${VAR} references)

The server is marked as deployed immediately.

### create_mcp_server

Scaffold a custom server directory. Creates:
- `mcp-servers/{name}/` directory for server code
- `mcp-servers/{name}.json` config with deployed=false

The agent then writes the server code (directly or via a coder sub-agent).

### deploy_mcp_server

Request deployment of a scaffolded server. Always requires human approval — the agent cannot deploy on its own. Returns server details for review. Human approves via POST /config/mcp-servers/{name}/deploy.

### list_mcp_servers

List all agent-managed servers with status. Supports semantic search via query parameter.

### stop_mcp_server

Stop a running agent-managed server. Cannot stop platform-configured servers.

## Building Custom MCP Servers

The typical flow:
1. Agent calls create_mcp_server(name, description)
2. Agent writes server code (e.g., Python FastMCP server) in the scaffolded directory
3. Agent calls deploy_mcp_server — gets HITL request
4. Human reviews and approves via API
5. Server connects and its tools register

Example: the platform built a microblog API MCP server by reading API docs, generating a FastMCP Python server, and deploying it with human approval.

## Environment Variable Resolution

MCP server configs support ${VAR_NAME} references that resolve from .env:

```json
{
  "env": {
    "API_KEY": "${MY_SECRET_KEY}"
  }
}
```

## Configuration

- `mcpServersDir` in lyra.config.json (default: ./mcp-servers)
- `mcpRequestTimeout` — timeout for MCP requests (default: 30s)
- Agent-managed servers connect at startup and on /config/reload
