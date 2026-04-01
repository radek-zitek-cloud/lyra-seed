# V1 Phase 3 — Smoke Tests

## Test Environment
- Prerequisites: V1 Phase 0–2 complete, `uv` installed
- Platform: must pass on both Linux (bash) and Windows (PowerShell)
- All LLM calls are mocked — no real API calls
- Run: `cd backend && uv run pytest tests/smoke/ -k "v1_phase_3" -v --tb=short`

## ST-3.1: Tool models and ToolProvider protocol
- **Validates:** Tool, ToolType, ToolResult models and ToolProvider protocol
- **Method:** Import and instantiate models, verify protocol shape
- **Checks:**
  - `ToolType` enum has MCP and PROMPT_MACRO values
  - `Tool` can be instantiated with name, description, input_schema, tool_type
  - `ToolResult` can be instantiated with success, output, duration_ms
  - `ToolProvider` protocol has `list_tools` and `call_tool` methods

## ST-3.2: ToolRegistry aggregates providers
- **Validates:** ToolRegistry combines tools from multiple providers
- **Method:** Create registry with two mock providers, verify aggregation
- **Checks:**
  - `list_tools()` returns combined tool list from all providers
  - `call_tool(name, args)` routes to the correct provider
  - Unknown tool name raises an error or returns error result
  - `get_tools_schema()` returns OpenAI-compatible JSON Schema list

## ST-3.3: PromptMacro model and provider
- **Validates:** PromptMacroProvider implements ToolProvider, expands templates
- **Method:** Create macro, register in provider, call it with mock LLM
- **Checks:**
  - `PromptMacro` model has name, template, parameters, description
  - Provider lists the macro as a tool
  - Calling the macro expands the template and calls the LLM
  - Returns result as ToolResult

## ST-3.4: Prompt macro SQLite repository
- **Validates:** CRUD for prompt macros in SQLite
- **Method:** Create temp DB, perform CRUD
- **Checks:**
  - Create, get, list, update, delete for PromptMacro entities
  - Template and parameters roundtrip correctly

## ST-3.5: Prompt macro CRUD API
- **Validates:** REST API for managing prompt macros
- **Method:** httpx AsyncClient with test app
- **Checks:**
  - `POST /macros` creates a macro, returns 201
  - `GET /macros` lists all macros
  - `GET /macros/{id}` returns macro details
  - `PUT /macros/{id}` updates a macro
  - `DELETE /macros/{id}` deletes a macro

## ST-3.6: MCPToolProvider (stub)
- **Validates:** MCP provider implements ToolProvider with configurable tools
- **Method:** Create provider with pre-configured mock tools
- **Checks:**
  - `list_tools()` returns configured tools
  - `call_tool()` invokes the configured handler
  - Returns ToolResult with success/failure

## ST-3.7: Agent runtime uses ToolRegistry
- **Validates:** Runtime dispatches tool calls through registry instead of stub
- **Method:** Create agent with mock LLM + registry with a test tool, run prompt
- **Checks:**
  - LLM receives tool list in its context
  - When LLM returns a tool call, runtime calls the tool via registry
  - Tool result is appended to conversation and sent back to LLM
  - TOOL_CALL and TOOL_RESULT events contain real tool output
  - Phase 2 tests still pass (backward compatibility)
