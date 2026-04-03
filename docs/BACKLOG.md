# Backlog

Items for future consideration, not tied to a specific phase.

---

### BL-001: delete_agent tool for parent-controlled child cleanup

**Context:** Parents can `dismiss_agent` (→ COMPLETED) and `stop_agent` (→ IDLE) but cannot delete a child agent programmatically. The `DELETE /agents/{id}` API exists but is not exposed as an agent tool.

**Scope:** Add a `delete_agent` tool to AgentSpawnerProvider that deletes the child agent and cleans up orphaned data (conversations, events, messages). Consider requiring HITL approval given the destructive nature.

**Priority:** Low — dismiss covers most lifecycle needs.

---

### BL-002: Per-agent MCP server configuration

**Context:** MCP servers are currently configured system-wide in `lyra.config.json` and shared by all agents via a single `ToolRegistry`. Every agent sees every tool. Consider allowing per-agent MCP server definitions in `prompts/{name}.json` so different agents get different tool sets (e.g., a coder agent gets filesystem+shell, a research agent gets web search, a restricted agent gets nothing).

**Scope:** Add optional `mcpServers` field to `AgentFileConfig`. On agent creation, merge agent-specific MCP servers with (or instead of) system-wide ones. May require per-agent `ToolRegistry` instances rather than a shared singleton — significant architectural change.

**Priority:** Medium — becomes important as agent specialization increases and for security (least-privilege tool access).
