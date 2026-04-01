# V1 Phase 3 — Plan

## Phase Reference
- **Version:** V1
- **Phase:** 3
- **Title:** Tool System
- **Roadmap Section:** §4, V1 Phase 3

## Prerequisites
- V1 Phase 0 (Project Skeleton & Tooling) — COMPLETE
- V1 Phase 1 (Abstractions & Event System) — COMPLETE
- V1 Phase 2 (Agent Runtime) — COMPLETE

## Deliverables Checklist
- [ ] `Tool` model, `ToolType` enum, `ToolResult` model
- [ ] `ToolProvider` protocol
- [ ] `ToolRegistry` — aggregates tools from multiple providers, resolves names
- [ ] `PromptMacro` model
- [ ] `PromptMacroProvider` implementing `ToolProvider`
- [ ] SQLite repository for prompt macros
- [ ] CRUD API for prompt macros
- [ ] MCP client provider (stub with mock-friendly interface)
- [ ] Wire `ToolRegistry` into `AgentRuntime` (replace stub tool execution)
- [ ] Tool calls emit events, tool list provided to LLM

## Implementation Steps

1. **Create tool models and protocol**
   - `backend/src/agent_platform/tools/models.py` — `Tool`, `ToolType`, `ToolResult`
   - `backend/src/agent_platform/tools/provider.py` — `ToolProvider` protocol

2. **Create ToolRegistry**
   - `backend/src/agent_platform/tools/registry.py` — `ToolRegistry` class
   - Aggregates tools from multiple `ToolProvider` instances
   - Resolves tool names to the correct provider
   - Provides combined tool list as JSON Schema for LLM context

3. **Create PromptMacro model and provider**
   - `backend/src/agent_platform/tools/prompt_macro.py` — `PromptMacro` model, `PromptMacroProvider`
   - Template expansion with `{{parameter}}` substitution
   - Calls LLM as a sub-call for macro execution
   - Returns result as `ToolResult`

4. **Create SQLite repository for prompt macros**
   - `backend/src/agent_platform/db/sqlite_macro_repo.py`
   - CRUD operations for `PromptMacro` entities

5. **Create MCP client provider (stub)**
   - `backend/src/agent_platform/tools/mcp_provider.py` — `MCPToolProvider`
   - Implements `ToolProvider` interface
   - Stub implementation that can be configured with tools for testing
   - Real MCP transport (stdio/SSE) left as future enhancement

6. **Create CRUD API for prompt macros**
   - `backend/src/agent_platform/api/macro_routes.py`
   - `POST /macros` — create macro
   - `GET /macros` — list macros
   - `GET /macros/{id}` — get macro
   - `PUT /macros/{id}` — update macro
   - `DELETE /macros/{id}` — delete macro

7. **Wire ToolRegistry into AgentRuntime**
   - Update `AgentRuntime` to accept a `ToolRegistry`
   - Replace stub tool execution with `registry.call_tool(name, args)`
   - Pass tool list to LLM via `tools` parameter in `complete()` call
   - Emit TOOL_CALL/TOOL_RESULT events with real results

8. **Update app factory**
   - Wire ToolRegistry, PromptMacroProvider into app startup
   - Register macro routes

## Dependencies & Libraries

No new dependencies. All existing:
- `pydantic` — models
- `aiosqlite` — SQLite storage
- `fastapi` — API routes

## File Manifest

### New files
- `backend/src/agent_platform/tools/models.py` — Tool, ToolType, ToolResult
- `backend/src/agent_platform/tools/provider.py` — ToolProvider protocol
- `backend/src/agent_platform/tools/registry.py` — ToolRegistry
- `backend/src/agent_platform/tools/prompt_macro.py` — PromptMacro, PromptMacroProvider
- `backend/src/agent_platform/tools/mcp_provider.py` — MCPToolProvider (stub)
- `backend/src/agent_platform/db/sqlite_macro_repo.py` — macro repo
- `backend/src/agent_platform/api/macro_routes.py` — macro CRUD API
- `backend/tests/smoke/test_v1_phase_3.py` — Phase 3 smoke tests

### Modified files
- `backend/src/agent_platform/core/runtime.py` — wire ToolRegistry, replace stub
- `backend/src/agent_platform/api/main.py` — register macro routes, wire registry
- `backend/src/agent_platform/api/_deps.py` — add tool registry access

## Risks & Decisions

- **MCP client:** Full MCP stdio/SSE transport is complex. Phase 3 implements a `MCPToolProvider` with a mock-friendly interface. The provider accepts pre-configured tools and can be swapped for a real MCP client later.
- **Prompt macro LLM calls:** The `PromptMacroProvider` needs an `LLMProvider` to execute macros. This is injected at construction time. In smoke tests, the LLM is mocked.
- **Tool list for LLM:** Tools are converted to OpenAI-compatible function calling JSON Schema format, since that's what OpenRouter expects.
- **Backward compatibility:** Phase 2 smoke tests create `AgentRuntime` without a `ToolRegistry`. The constructor will default to an empty registry to avoid breaking existing tests.
