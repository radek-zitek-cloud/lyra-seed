# V2 Phase 4 — COMPLETE

## Current State
- Started: 2026-04-03
- Completed: 2026-04-03

## Smoke Test Results
| ID | Description | Status | Notes |
|----|-------------|--------|-------|
| ST-V2-4.1 | AgentConfig allowed_mcp_servers | PASS | |
| ST-V2-4.2 | AgentFileConfig allowed_mcp_servers | PASS | |
| ST-V2-4.3 | ToolRegistry MCP server filtering | PASS | |
| ST-V2-4.4 | ToolRegistry allowed_tools filtering | PASS | |
| ST-V2-4.5 | Combined filtering | PASS | |
| ST-V2-4.6 | Runtime uses agent scope | PASS | |
| ST-V2-4.7 | Config resolution from file | PASS | |
| ST-V2-4.8 | allowed_tools enforcement | PASS | |
| ST-V2-4.9 | Child inherits parent scope | PASS | |
| ST-V2-4.10 | Child template overrides scope | PASS | |
| ST-V2-4.11 | CONFIGURATION_GUIDE.md exists | PASS | |

## Iteration Log
### Iteration 1
- Implemented all deliverables: model fields, registry filtering, runtime wiring, config resolution, child inheritance, CONFIGURATION_GUIDE.md
- All 11 smoke tests passed
- Fixed import sorting (ruff I001)
- Full regression test: 121/121 tests pass across all phases

## Blockers Encountered
- None

## Decisions Made
- Filtering happens at schema level only — ToolRegistry still routes any call. Security is by not showing tools to the LLM.
- `allowed_mcp_servers: None` means all servers (backwards compatible). Empty list means no MCP tools.
- Core tools (memory, spawner, orchestration, macros) are never filtered by MCP server scoping — only `allowed_tools` can filter those.
- Both filters apply simultaneously when set — a tool must pass both.
