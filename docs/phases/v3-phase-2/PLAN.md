# V3 Phase 2 — Plan

## Phase Reference
- **Version:** V3
- **Phase:** 2
- **Title:** Tool Creation — MCP Servers
- **Roadmap Section:** V3P2

## Prerequisites
- [x] V3 Phase 1: Tool Creation — Skills — COMPLETE

## Deliverables Checklist
- [ ] 2.1: `mcp-servers/` directory with JSON config files for agent-managed MCP servers
- [ ] 2.2: `MCPServerManager` — loads configs, connects/disconnects servers, hot-reload
- [ ] 2.3: `add_mcp_server` tool — add a pre-built MCP server from npm/pip package
- [ ] 2.4: `create_mcp_server` tool — scaffold a custom Python MCP server in `mcp-servers/{name}/`
- [ ] 2.5: `deploy_mcp_server` tool — validate, start, and register a scaffolded server (HITL gated)
- [ ] 2.6: `list_mcp_servers` tool — show running and available servers with semantic search
- [ ] 2.7: `stop_mcp_server` tool — stop a running agent-managed server
- [ ] 2.8: Hot-reload — `/config/reload` reconnects new servers, disconnects removed
- [ ] 2.9: Config editor shows `mcp-servers/` section
- [ ] 2.10: Update system prompt with MCP server management tools

## Implementation Steps

### 1. Create mcp-servers/ directory and config format
**Files:** `mcp-servers/` directory

Config format (`mcp-servers/{name}.json`):
```json
{
  "name": "microblog-api",
  "description": "CRUD operations for the microblog platform",
  "command": "uv",
  "args": ["run", "python", "server.py"],
  "workdir": "mcp-servers/microblog-api",
  "env": {"API_URL": "${MICROBLOG_API_URL}"},
  "managed": true,
  "deployed": false
}
```

Fields:
- `managed: true` — agent-managed (vs platform config `lyra.config.json`)
- `deployed: false` — scaffolded but not yet running (awaiting HITL approval)
- `workdir` — for scaffolded servers, the project directory

### 2. MCPServerManager
**Files:** `backend/src/agent_platform/tools/mcp_server_manager.py`

Responsibilities:
- Scan `mcp-servers/` for `.json` configs at startup
- Connect deployed servers via `MCPStdioClient`
- Register tools with `MCPClientProvider`
- Support hot-reload: scan for new/removed configs, connect/disconnect accordingly
- Track server status (running, stopped, pending deployment)

### 3. add_mcp_server tool
**Files:** `backend/src/agent_platform/tools/mcp_server_manager.py`

- Writes a `.json` config to `mcp-servers/{name}.json`
- Sets `managed: true, deployed: true`
- Connects the server immediately via MCPStdioClient
- Registers new tools in the registry
- Uses agent's HITL policy (consistent with other tool calls)
- Validates name format (same regex as skills)

### 4. create_mcp_server tool
**Files:** `backend/src/agent_platform/tools/mcp_server_manager.py`

- Creates `mcp-servers/{name}/` directory
- Writes a `.json` config with `deployed: false`
- Returns the directory path for the agent to populate with code
- Does NOT deploy — agent writes code, then calls `deploy_mcp_server`
- The agent decides how to build: direct file writes, spawn coder, etc.

### 5. deploy_mcp_server tool
**Files:** `backend/src/agent_platform/tools/mcp_server_manager.py`

- **Always requires HITL approval** regardless of agent's HITL policy
- Shows: server name, description, command, env vars, tool list preview
- After approval: starts the server, discovers tools, registers in registry
- Updates config: `deployed: true`
- If server fails to start, returns error with stderr

### 6. list_mcp_servers tool
**Files:** `backend/src/agent_platform/tools/mcp_server_manager.py`

- Lists all agent-managed servers with status (running/stopped/pending)
- Also lists platform-configured servers (from lyra.config.json) as read-only
- Optional `query` parameter for semantic search over descriptions
- Uses embedding provider (same pattern as skills/templates)

### 7. stop_mcp_server tool
**Files:** `backend/src/agent_platform/tools/mcp_server_manager.py`

- Stops a running agent-managed server
- Cannot stop platform-configured servers (from lyra.config.json)
- Removes tools from registry
- Updates config or keeps it for future restart

### 8. Hot-reload integration
**Files:** `backend/src/agent_platform/api/config_routes.py`, `main.py`

- `/config/reload` extended to scan `mcp-servers/` directory
- New deployed configs → connect server, register tools
- Removed configs → disconnect server, unregister tools
- Changed configs → disconnect old, connect new

### 9. Config editor integration
**Files:** `backend/src/agent_platform/api/config_routes.py`

- Add `mcp_servers` section to `/config/files` listing `mcp-servers/*.json`

### 10. System prompt
**Files:** `prompts/default.md`

- Document `add_mcp_server`, `create_mcp_server`, `deploy_mcp_server`, `list_mcp_servers`, `stop_mcp_server`
- Guidance: search web for existing MCP packages before building custom

## File Manifest
**New:**
- `backend/src/agent_platform/tools/mcp_server_manager.py` — MCPServerManager + tools
- `mcp-servers/` — directory for agent-managed server configs
- `backend/tests/smoke/test_v3_phase_2.py` — smoke tests

**Modified:**
- `backend/src/agent_platform/api/main.py` — wire MCPServerManager
- `backend/src/agent_platform/api/config_routes.py` — add mcp_servers to file listing, reload support
- `backend/src/agent_platform/api/_deps.py` — add mcp_server_manager getter
- `prompts/default.md` — document new tools

## Risks & Decisions
- `deploy_mcp_server` always HITL-gated — running agent-created code is the highest-risk operation
- Agent-managed servers run as subprocesses — same as platform MCP servers, no additional sandboxing
- Server configs in `mcp-servers/` are separate from `lyra.config.json` — clean separation
- `${VAR}` env var resolution reused from existing MCP config loading
- For scaffolded servers, the agent is responsible for writing valid MCP server code — the platform just manages lifecycle
