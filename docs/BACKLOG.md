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

---

### BL-005: Orchestration subtasks can use tools or spawn sub-agents

**Context:** Orchestration subtasks currently execute as single LLM calls — prompt in, text out. They have no tool access, no memory, no conversation history. The `assigned_to` field on each `SubTask` exists in the model but is ignored during execution; every subtask runs the same way regardless of what it's assigned to.

The original V2P3 roadmap specified "each subtask mapped to: existing tool, existing skill, or new sub-agent" but the implementation took the simpler direct-LLM approach, which proved sufficient for knowledge-work tasks (analysis, research, writing).

**Scope:** When `assigned_to` is a tool name (e.g., `shell`, `read_file`), execute it via the `ToolRegistry` instead of an LLM call. When `assigned_to` is `spawn_agent`, create an actual child agent with full runtime capabilities (tools, memory, multi-iteration loop) and collect its result. This would allow orchestrated subtasks to interact with the filesystem, run commands, query APIs, or perform complex multi-step work.

**Considerations:**
- Sub-agent subtasks would be significantly slower (full runtime loop vs single LLM call)
- Parallel sub-agent spawning needs concurrency limits to avoid resource exhaustion
- Tool-based subtasks need input/output mapping (tool arguments from subtask description, tool result as subtask output)
- HITL policies on sub-agent subtasks need to be defined (inherit parent? independent?)

**Priority:** Medium — the current LLM-only approach handles analysis/writing tasks well, but tool access would unlock orchestration of tasks that require real-world interaction (code generation, file processing, API calls).

---

### BL-006: Live orchestration graph visualization

**Context:** Orchestration runs take 1–2 minutes and involve multiple parallel/sequential LLM calls, sub-agent spawns, and message flows. Currently the only way to observe progress is the event timeline — a flat chronological list of events. A graph view would make the orchestration structure, dependencies, progress, and agent relationships immediately visible.

**Concept:** A real-time node-edge graph where:
- Each agent is a container box showing name, model, and status
- Orchestration subtasks appear as nodes inside the agent box, colored by status (pending/running/completed/failed/skipped)
- Dependency edges connect subtasks within an agent (from the plan's `dependencies` field)
- Parent-child relationships link agent boxes (from `parent_agent_id`)
- Inter-agent messages show as labeled edges between agent boxes (from message events)
- Auto-synthesis by the platform shown as a final node after all subtasks converge
- Everything updates in real-time as SSE events arrive

**Tech:** React Flow (compound nodes, custom styling, animated edges, Dagre/ELK auto-layout). All required data already streams via SSE — no backend changes needed for the basic version.

**Scope tiers:**
1. Basic — agent boxes with subtask nodes, dependency edges, real-time status colors
2. Enhanced — parent-child agent links, message flow edges, spawn animations, pipeline progress
3. Full — timeline scrubber for historical replay, click-to-expand agent details, duration overlays

**Priority:** Low — quality of life. The event timeline works for debugging; this is about making orchestration intuitive and visually impressive.
