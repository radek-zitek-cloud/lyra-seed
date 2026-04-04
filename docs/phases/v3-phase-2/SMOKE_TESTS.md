# V3 Phase 2 — Smoke Tests

## Test Environment
- Prerequisites: V3P1 complete, all prior smoke tests passing
- LLM calls: always mocked
- MCP servers: mocked (no real subprocess spawning in tests)
- External APIs: never called

## Backend Smoke Tests

### ST-V3-2.1: MCPServerManager loads configs from directory
- **Validates:** Config scanning
- **Method:** Create temp dir with JSON config files, init manager
- **Checks:**
  - Manager discovers config files
  - Parses name, description, command, deployed status
  - Skips non-JSON files

### ST-V3-2.2: add_mcp_server writes config and returns success
- **Validates:** Adding a pre-built MCP server
- **Method:** Call add_mcp_server with package details
- **Checks:**
  - JSON config file written to mcp-servers/{name}.json
  - Config has managed=true, deployed=true
  - Name validation (rejects invalid names)
  - Duplicate name rejected

### ST-V3-2.3: create_mcp_server scaffolds directory
- **Validates:** Custom server scaffolding
- **Method:** Call create_mcp_server with name and description
- **Checks:**
  - Directory created at mcp-servers/{name}/
  - Config written with deployed=false
  - Returns path for agent to populate
  - Does NOT attempt to connect/deploy

### ST-V3-2.4: deploy_mcp_server requires HITL
- **Validates:** HITL gate on deployment
- **Method:** Call deploy_mcp_server, check that it forces HITL
- **Checks:**
  - Tool returns HITL-required indicator even with hitl_policy=never
  - Config shows deployed=false until approved
  - After approval simulation, config updates to deployed=true

### ST-V3-2.5: list_mcp_servers returns managed and platform servers
- **Validates:** Server listing
- **Method:** Set up managed configs + mock platform servers
- **Checks:**
  - Returns both managed and platform servers
  - Each entry has: name, description, status, managed flag
  - Managed servers show deployed status
  - Platform servers show as read-only

### ST-V3-2.6: list_mcp_servers semantic search
- **Validates:** Query-based search
- **Method:** Create servers with distinct descriptions, mock embeddings
- **Checks:**
  - Query ranks relevant servers first
  - Without query returns all

### ST-V3-2.7: stop_mcp_server stops managed server
- **Validates:** Server lifecycle
- **Checks:**
  - Running managed server can be stopped
  - Platform servers cannot be stopped (error returned)
  - Config retained after stop

### ST-V3-2.8: Config editor lists mcp-servers section
- **Validates:** UI integration
- **Method:** Create mcp-servers dir with configs, call /config/files
- **Checks:**
  - Response includes mcp_servers category
  - Lists .json files from mcp-servers/

### ST-V3-2.9: Reload reconnects new servers
- **Validates:** Hot-reload
- **Method:** Add a config file, call reload, check server list
- **Checks:**
  - New deployed config detected on reload
  - Server appears in list after reload

### ST-V3-2.10: MCP server config with ${VAR} env resolution
- **Validates:** Env var expansion
- **Method:** Config with ${TEST_VAR} in env, set os.environ
- **Checks:**
  - Resolved value used, not literal ${TEST_VAR}
