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

**Priority:** Medium — becomes important as agent specialization increases and for security (least-privilege tool access). Additional motivation: every tool in the registry adds to the tools schema sent to the LLM on every call, inflating context size and token costs. A worker that only needs filesystem tools currently receives 38+ tool definitions. Per-agent tool scoping would significantly reduce per-call token overhead.

**Scheduled:** V2 Phase 4 (see `ROADMAP.md`).

---

### BL-003: EventBus filtering by event name and module

**Context:** Currently all EventBus subscribers receive all events. As the system grows, agents and services may only care about specific event types or events from specific modules.

**Scope:** Add two independent filtering dimensions to EventBus subscriptions: (1) filter by event name (e.g., subscribe only to `agent.status_changed`), and (2) filter by source module (e.g., subscribe only to events from `orchestrator`). Filters should be composable — a subscriber can specify either, both, or neither (wildcard). Filtering should happen at the bus level before dispatch, not in each subscriber.

**Priority:** Low — current event volume is manageable, but will become important as agent count and event throughput grow.

---

### BL-004: LLM-assisted HITL mode (middle ground between always-approve and auto-approve)

**Context:** HITL currently operates as a binary choice: either every tool call requires human approval, or it runs automatically. Neither extreme scales well — full HITL is tedious for routine operations, while auto-approve removes the safety net for destructive actions.

**Scope:** Add a third HITL mode where an LLM evaluates each tool call against configurable safety criteria and decides whether it can proceed automatically or needs human approval. For example, a `read_file` call would auto-approve, while `delete_agent` or shell commands with `rm` would escalate to the human. The safety policy should be configurable (e.g., via a prompt or rule set describing what is considered safe). Consider cost/latency tradeoffs of the extra LLM call per tool invocation — a smaller/faster model or cached rule matching may be preferable.

**Priority:** Medium — improves usability as agent autonomy increases without sacrificing safety.
