# V2 Phase 4 — Plan

## Phase Reference
- **Version:** V2
- **Phase:** 4
- **Title:** Per-Agent Tool Scoping
- **Roadmap Section:** §589-621

## Prerequisites
- [x] V2 Phase 3: Orchestration Patterns — COMPLETE

## Deliverables Checklist
- [ ] 4.1: `allowed_mcp_servers` field in AgentFileConfig and AgentConfig
- [ ] 4.2: ToolRegistry filtering — `get_tools_schema()` and `list_tools()` accept allowed server list
- [ ] 4.3: Config resolution — agent creation resolves `allowed_mcp_servers` from file config / platform config
- [ ] 4.4: Runtime passes agent's allowed servers when building tool schema
- [ ] 4.5: `allowed_tools` enforcement — explicit tool whitelist (existing field, needs wiring)
- [ ] 4.6: Child agents inherit parent's tool scope, template can override
- [ ] 4.7: `docs/CONFIGURATION_GUIDE.md` — comprehensive configuration reference

## Implementation Steps

### 1. Add `allowed_mcp_servers` to config models
**Files:** `core/models.py`, `core/platform_config.py`

- Add `allowed_mcp_servers: list[str] | None = None` to `AgentConfig`
  - `None` means "all servers" (backwards compatible)
  - Empty list `[]` means "no MCP servers"
  - `["filesystem"]` means "only filesystem server"
- Add `allowed_mcp_servers: list[str] | None = None` to `AgentFileConfig`
- No change to `PlatformConfig` — platform defines available servers, agent config scopes access

### 2. Add filtering to ToolRegistry
**Files:** `tools/registry.py`

- Add `get_tools_schema(allowed_mcp_servers=None, allowed_tools=None)` parameters
- Add `list_tools(allowed_mcp_servers=None, allowed_tools=None)` parameters
- When `allowed_mcp_servers` is set, filter out MCP tools whose `source` is not in the list
- When `allowed_tools` is set, filter to only those tool names
- Core tools (memory, spawner, orchestration, macros) are never filtered by MCP server list
- `call_tool()` unchanged — routing still works for any registered tool (agent can't call tools not in its schema, but the registry doesn't block at execution level)

### 3. Wire config resolution
**Files:** `api/routes.py`

- Read `allowed_mcp_servers` from file config during agent creation
- Read `allowed_tools` from file config during agent creation
- No platform-level default for `allowed_mcp_servers` — `None` (all servers) is the default

### 4. Pass scope to runtime
**Files:** `core/runtime.py`

- In the agent loop, pass `agent.config.allowed_mcp_servers` and `agent.config.allowed_tools` to `get_tools_schema()`
- This scopes what the LLM sees without changing tool execution

### 5. Enforce `allowed_tools` at schema level
**Files:** `core/runtime.py`

- If `agent.config.allowed_tools` is non-empty, only include those tool names in the schema
- This is additive with MCP server filtering — both filters apply

### 6. Child agent tool inheritance
**Files:** `tools/agent_spawner.py`

- In `_resolve_child_config`: if child's template doesn't specify `allowed_mcp_servers`, inherit from parent
- If template does specify it, use the template's value (override)
- Same logic for `allowed_tools`

### 7. Configuration Guide
**Files:** `docs/CONFIGURATION_GUIDE.md`

- Document all config surfaces: `.env`, `lyra.config.json`, `prompts/{name}.json`, `prompts/{name}.md`, `prompts/system/*.md`
- Document the four-level resolution chain
- Document every field with defaults and purpose
- Include examples for common agent roles

## File Manifest
- `backend/src/agent_platform/core/models.py` — add `allowed_mcp_servers` to AgentConfig
- `backend/src/agent_platform/core/platform_config.py` — add `allowed_mcp_servers` to AgentFileConfig
- `backend/src/agent_platform/tools/registry.py` — add filtering to list_tools/get_tools_schema
- `backend/src/agent_platform/core/runtime.py` — pass agent scope to tool schema
- `backend/src/agent_platform/api/routes.py` — resolve allowed_mcp_servers from file config
- `backend/src/agent_platform/tools/agent_spawner.py` — child inherits parent scope
- `docs/CONFIGURATION_GUIDE.md` — new comprehensive guide
- `backend/tests/smoke/test_v2_phase_4.py` — smoke tests

## Risks & Decisions
- Filtering happens at schema level only — the registry still routes any call. This is intentional: if an agent somehow knows a tool name outside its scope, the call works. Security is enforced by not showing the tool to the LLM, not by blocking execution.
- `allowed_mcp_servers: None` means all servers (backwards compatible). Empty list `[]` means no MCP servers at all.
- Core tools (memory, spawner, orchestration, macros) are never filtered by MCP server scoping — only MCP tools are. `allowed_tools` can filter anything including core tools.
