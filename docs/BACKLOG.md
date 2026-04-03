# Backlog

Items for future consideration, not tied to a specific phase.

---

### BL-001: delete_agent tool for parent-controlled child cleanup

**Context:** Parents can `dismiss_agent` (→ COMPLETED) and `stop_agent` (→ IDLE) but cannot delete a child agent programmatically. The `DELETE /agents/{id}` API exists but is not exposed as an agent tool.

**Scope:** Add a `delete_agent` tool to AgentSpawnerProvider that deletes the child agent and cleans up orphaned data (conversations, events, messages). Consider requiring HITL approval given the destructive nature.

**Priority:** Low — dismiss covers most lifecycle needs.

---

### ~~BL-002: Per-agent MCP server configuration~~ DONE

Delivered in V2 Phase 4 as `allowed_mcp_servers` and `allowed_tools` config fields. See `ROADMAP.md` V2P4 and `docs/CONFIGURATION_GUIDE.md`.

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

### ~~BL-005: Orchestration subtasks can use tools or spawn sub-agents~~ DONE

Delivered in V2 Phase 6. `_execute_subtask()` dispatches on `assigned_to`: `"spawn_agent"` spawns child agents, tool names call via registry, everything else falls back to LLM.

---

### ~~BL-006: Live orchestration graph visualization~~ DONE

Delivered in V2 Phase 5 (deliverables 5.1–5.3). The Full tier's timeline scrubber split out as BL-007.

---

### BL-007: Orchestration timeline scrubber and historical replay

**Context:** The graph view (V2P5) shows live orchestration state. A timeline scrubber would allow rewinding to any point in a past orchestration run — useful for post-mortem analysis, demos, and understanding how a complex multi-agent task unfolded step by step.

**Scope:** Add a scrubber control to the graph view that replays historical SSE events at adjustable speed. At each point in time, the graph reflects the state as it was: agent statuses, subtask progress, message flows, and spawn events. Clicking on a node at any replay point opens the agent detail at that moment. Duration overlays show how long each subtask and agent turn took.

**Considerations:**
- Requires persisted event history with precise timestamps (already available via `GET /agents/{id}/events`)
- Graph state must be reconstructable from events alone (no snapshots needed — events are the source of truth)
- Playback speed control: 1x, 2x, 5x, 10x, and step-by-step
- May need a "session" concept to group events belonging to one orchestration run

**Priority:** Low — quality of life for debugging and demos. The live graph from V2P5 covers the primary use case.
