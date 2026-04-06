# Backlog

Items for future consideration, not tied to a specific phase.

---

### ~~BL-001: delete_agent tool for parent-controlled child cleanup~~ DONE

Delivered as `delete_agent` tool in AgentSpawnerProvider. Deletes child agent and cleans up conversations, messages, and events. Only allows deleting own children. Cancels running tasks before deletion.

---

### ~~BL-002: Per-agent MCP server configuration~~ DONE

Delivered in V2 Phase 4 as `allowed_mcp_servers` and `allowed_tools` config fields. See `ROADMAP.md` V2P4 and `docs/CONFIGURATION_GUIDE.md`.

---

### BL-003: EventBus filtering by event name and module — PARTIAL

**Delivered:** Frontend event inspector with toggleable filter chips for event types and modules, persisted to localStorage. Covers the user-facing need.

**Not delivered:** Server-side bus-level filtering before dispatch. All subscribers still receive all events. Not needed at current scale but will matter as agent count and event throughput grow.

**Remaining scope:** Add `event_types` and `modules` filter parameters to `event_bus.subscribe()`. Filter at the bus level before enqueuing to subscriber queues.

**Priority:** Low — frontend filtering handles the UX. Server-side becomes important at high event volume.

---

### BL-004: LLM-assisted HITL mode (middle ground between always-approve and auto-approve)

**Status:** Not implemented. The `dangerous_only` policy exists in the `HITLPolicy` enum but the runtime has no branch for it — it falls through to `never` (auto-approve all). No rule-based or LLM-assisted tool classification exists.

**Context:** HITL currently operates as a binary choice: either every tool call requires human approval, or it runs automatically. Neither extreme scales well — full HITL is tedious for routine operations, while auto-approve removes the safety net for destructive actions.

**Scope:** Implement the `dangerous_only` policy with a configurable tool classification. Options in increasing sophistication:

1. **Hardcoded list** — classify tools as safe/dangerous at registration (e.g., `shell_execute` = dangerous, `recall` = safe). Cheapest, no LLM cost.
2. **Rule-based** — configurable patterns (e.g., "any tool with `delete` or `execute` in the name requires approval"). More flexible.
3. **LLM-assisted** — an LLM evaluates each tool call against safety criteria. Most flexible but adds cost/latency per tool call. Consider smaller/faster model or cached decisions.

**Priority:** Medium — improves usability as agent autonomy increases without sacrificing safety.

---

### ~~BL-005: Orchestration subtasks can use tools or spawn sub-agents~~ DONE

Delivered in V2 Phase 6. `_execute_subtask()` dispatches on `assigned_to`: `"spawn_agent"` spawns child agents, tool names call via registry, everything else falls back to LLM.

---

### ~~BL-006: Live orchestration graph visualization~~ DONE

Delivered in V2 Phase 5 (deliverables 5.1–5.3). The Full tier's timeline scrubber split out as BL-007.

---

### BL-007: Orchestration timeline scrubber and historical replay

**Status:** Not started.

**Context:** The graph view (V2P5) shows live orchestration state. A timeline scrubber would allow rewinding to any point in a past orchestration run — useful for post-mortem analysis, demos, and understanding how a complex multi-agent task unfolded step by step.

**Scope:** Add a scrubber control to the graph view that replays historical SSE events at adjustable speed. At each point in time, the graph reflects the state as it was: agent statuses, subtask progress, message flows, and spawn events. Clicking on a node at any replay point opens the agent detail at that moment. Duration overlays show how long each subtask and agent turn took.

**Considerations:**
- Requires persisted event history with precise timestamps (already available via `GET /agents/{id}/events`)
- Graph state must be reconstructable from events alone (no snapshots needed — events are the source of truth)
- Playback speed control: 1x, 2x, 5x, 10x, and step-by-step
- May need a "session" concept to group events belonging to one orchestration run

**Priority:** Low — quality of life for debugging and demos. The live graph from V2P5 covers the primary use case.

---

### BL-008: Unified RAG-based capability discovery — PARTIAL

**Delivered:** The `discover` tool (V4P3) searches across skills, templates, MCP tools, knowledge base, and memories in a single call. Returns ranked results with source attribution.

**Not delivered:** On-demand tool schema injection. All tools (~48+) are still sent in every LLM call regardless of relevance, consuming tokens. The envisioned "discover then use" pattern — where only core tools + `discover` are sent by default, and discovered tools are dynamically added to the schema — is not implemented.

**Remaining scope:**
- Send only core tools (memory, spawner, discover) by default
- Agent calls `discover(query="...")` to find relevant tools on demand
- Discovered tools are added to the schema for subsequent iterations in that turn
- Cache discovered tools for the conversation lifetime
- Backward compatibility: agents with `allowed_tools` still get their tools directly

**Priority:** Medium — the token savings would be significant. Currently ~48 tool schemas are sent every call (~2-3k tokens). On-demand discovery would reduce this to ~10 core tools + discovered ones.
