# V2 Phase 4 — Smoke Tests

## Test Environment
- Prerequisites: V2P3 complete, all prior smoke tests passing
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-V2-4.1: AgentConfig has allowed_mcp_servers field
- **Validates:** Model fields exist
- **Checks:**
  - `AgentConfig.allowed_mcp_servers` defaults to `None`
  - Can be set to a list of strings
  - Can be set to empty list

### ST-V2-4.2: AgentFileConfig has allowed_mcp_servers field
- **Validates:** File config model
- **Checks:**
  - `AgentFileConfig.allowed_mcp_servers` defaults to `None`
  - Parses from JSON correctly

### ST-V2-4.3: ToolRegistry filters by allowed_mcp_servers
- **Validates:** Schema filtering
- **Method:** Register MCP-type tools with different sources, call `list_tools` with filter
- **Checks:**
  - `list_tools()` with no filter returns all tools
  - `list_tools(allowed_mcp_servers=["filesystem"])` returns only filesystem MCP tools plus all non-MCP tools
  - `list_tools(allowed_mcp_servers=[])` returns only non-MCP tools
  - `get_tools_schema()` respects the same filtering

### ST-V2-4.4: ToolRegistry filters by allowed_tools
- **Validates:** Tool name whitelist
- **Method:** Register multiple tools, call with allowed_tools filter
- **Checks:**
  - `list_tools(allowed_tools=["remember", "recall"])` returns only those two
  - `get_tools_schema(allowed_tools=["remember"])` returns only that one

### ST-V2-4.5: Combined MCP server and tool name filtering
- **Validates:** Both filters work together
- **Checks:**
  - When both `allowed_mcp_servers` and `allowed_tools` are set, both filters apply
  - A tool must pass both filters to be included

### ST-V2-4.6: Runtime uses agent's allowed_mcp_servers for tool schema
- **Validates:** End-to-end scoping in agent loop
- **Method:** Create agent with `allowed_mcp_servers=["filesystem"]`, mock LLM, run
- **Checks:**
  - LLM receives tool schema with only filesystem MCP tools (not shell)
  - Core tools (memory, spawner) still present

### ST-V2-4.7: Agent creation resolves allowed_mcp_servers from file config
- **Validates:** Config resolution chain
- **Method:** Create app, create agent whose template specifies `allowed_mcp_servers`
- **Checks:**
  - Agent's config has the resolved `allowed_mcp_servers`

### ST-V2-4.8: allowed_tools enforcement scopes tool schema
- **Validates:** Explicit tool whitelist
- **Method:** Create agent with `allowed_tools=["remember", "recall"]`, run
- **Checks:**
  - LLM receives only the whitelisted tools
  - No MCP, spawner, or orchestration tools in schema

### ST-V2-4.9: Child agent inherits parent's tool scope
- **Validates:** Tool scope inheritance
- **Method:** Parent has `allowed_mcp_servers=["filesystem"]`, spawns child without template
- **Checks:**
  - Child's config has `allowed_mcp_servers=["filesystem"]`

### ST-V2-4.10: Child template overrides parent's tool scope
- **Validates:** Template override
- **Method:** Parent has `allowed_mcp_servers=["filesystem"]`, spawns child with template that specifies different servers
- **Checks:**
  - Child uses template's `allowed_mcp_servers`, not parent's

### ST-V2-4.11: CONFIGURATION_GUIDE.md exists and covers key topics
- **Validates:** Documentation completeness
- **Checks:**
  - File exists at `docs/CONFIGURATION_GUIDE.md`
  - Contains sections for: .env, lyra.config.json, agent JSON config, agent system prompts, system prompts, resolution chain
  - References `allowed_mcp_servers` and `allowed_tools`
