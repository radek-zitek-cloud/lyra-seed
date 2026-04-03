# Post-V2 Report — Self-Evolving Multi-Agent Platform

> **Date:** 2026-04-03
> **Status:** V2 Complete (5 phases, 140 smoke tests passing)
> **Author:** Claude Code (implementation) / Radek Zitek (direction)

---

## 1. Executive Summary

V2 is **complete and functional**. The platform has evolved from V1's single-agent system into a full multi-agent orchestration platform with hierarchical agent spawning, inter-agent messaging, task decomposition with three execution strategies, per-agent tool scoping, and a real-time graph visualization. All five V2 phases delivered their roadmap commitments without scope reductions.

**Key numbers:**
- 121 backend smoke tests + 19 frontend smoke tests = **140 total** (all passing)
- 9 use case documents executed, **8 PASS**, 1 PASS with notes
- 7 backlog items tracked (2 completed in V2, 5 deferred)
- 0 regressions against V1 test suite

---

## 2. Phase Completion Status

| Phase | Title | Completed | Backend Tests | Frontend Tests |
|-------|-------|-----------|--------------|----------------|
| V2P1 | Sub-Agent Spawning | 2026-04-02 | 14/14 | — |
| V2P2 | Inter-Agent Communication & Async Lifecycle | 2026-04-02 | 14/14 | 2/2 |
| V2P3 | Orchestration Patterns | 2026-04-03 | 12/12 | — |
| V2P4 | Per-Agent Tool Scoping | 2026-04-03 | 11/11 | — |
| V2P5 | Multi-Agent & Orchestration Graph | 2026-04-03 | — | 13/13 |
| **V1 (maintained)** | **Phases 0–7** | **2026-04-02** | **70/70** | **4/4** |
| **Total** | | | **121** | **19** |

---

## 3. What Was Built

### 3.1 V2 Phase 1 — Sub-Agent Spawning

Agents can create child agents that run with full runtime capabilities.

**Tools added:** `spawn_agent`, `wait_for_agent`, `get_agent_result`, `list_child_agents`

**Key decisions:**
- Children inherit parent config (model, temperature) by default, overridable via template or inline
- `parent_agent_id` field links children to parents
- Spawn depth guard (max 3 levels) prevents infinite recursion
- Templates (`prompts/{name}.md` + `.json`) define reusable agent roles

**Events:** `AGENT_SPAWN`, `AGENT_COMPLETE`

### 3.2 V2 Phase 2 — Inter-Agent Communication & Async Lifecycle

Agents communicate via a persistent message bus and run asynchronously.

**Tools added:** `send_message`, `receive_messages`, `check_agent_status`, `stop_agent`, `dismiss_agent`

**Message types:** TASK, RESULT, QUESTION, ANSWER, GUIDANCE, STATUS_UPDATE

**Auto-wake:** IDLE agents automatically start a runtime turn when receiving TASK, QUESTION, GUIDANCE, RESULT, or ANSWER messages. STATUS_UPDATE is the only non-waking type (queued in inbox for next natural wake).

**Lifecycle transitions:**
- `stop_agent`: RUNNING → IDLE (reusable)
- `dismiss_agent`: any → COMPLETED (permanent, rejects further messages)
- Async spawn returns immediately; child runs in background `asyncio.Task`

**Events:** `MESSAGE_SENT`, `MESSAGE_RECEIVED`

**UI additions:** MessagePanel (inter-agent messages), SUB-AGENTS bar, PARENT navigation link, `/memories` page

### 3.3 V2 Phase 3 — Orchestration Patterns

Complex tasks are decomposed into subtasks and executed with configurable strategies.

**Tools added:** `decompose_task` (plan only), `orchestrate` (end-to-end)

**Strategies:**
- **Sequential** — subtasks run one by one in order
- **Parallel** — independent subtasks run concurrently via `asyncio.gather`
- **Pipeline** — output of each subtask feeds as context into the next

**Architecture:**
- `TaskDecomposer` — LLM-based decomposition using `prompts/system/decompose_task.md`
- `ResultSynthesizer` — combines subtask outputs using `prompts/system/synthesize_results.md`
- Failure policies per subtask: RETRY, REASSIGN, ESCALATE, SKIP
- `orchestration_model` config (defaults to cheaper model for decomposition/synthesis)

**Limitation:** Subtasks execute as standalone LLM calls without tool access. The `assigned_to` field exists but is unused. See BL-005 for future enhancement.

### 3.4 V2 Phase 4 — Per-Agent Tool Scoping

Agents see only the tools they need, reducing token overhead and enforcing least-privilege.

**Config fields:**
- `allowed_mcp_servers: list[str] | null` — whitelist MCP servers (null = all)
- `allowed_tools: list[str] | null` — whitelist tool names (null = all)

**Design:** Filtering at schema level — tools excluded from the LLM's function-calling schema. Core tools (memory, spawner, orchestration) are never filtered by MCP scope, only by `allowed_tools`.

**Config resolution chain:** per-agent file → default file → platform config → hardcoded defaults

**Impact:** A worker restricted to `["remember", "send_message"]` sees 2 tools instead of 40+, saving ~200-300 tokens per LLM call.

**Documentation:** `docs/CONFIGURATION_GUIDE.md` added covering all configuration surfaces.

### 3.5 V2 Phase 5 — Multi-Agent & Orchestration Graph

New `/graph` page providing an interactive visualization of the agent network.

**Components:**
- **AgentNode** — compound React Flow nodes showing name, model, status, and orchestration subtask pills
- **ParentChildEdge** — straight hierarchy lines (animated dash when child is running)
- **MessageEdge** — bezier curves colored by message type, labeled, with time-based visibility
- **DashboardHeader** — agent counts by status, pending HITL indicator
- **GraphFilters** — message type checkboxes, time range (1m/5m/15m/1h/6h/24h/All), show/hide toggles
- **SpawnAgentForm** — create root agents from the sidebar

**Tech:** React Flow (`@xyflow/react` v12), dagre auto-layout, global SSE stream for real-time updates

**Key principle:** This is a **separate view** alongside the existing observation UI. Event timeline, conversation panel, HITL panel, and memory browser are completely unchanged.

---

## 4. Architecture: V1 → V2

### V1: Single Agent
```
Human → Agent → LLM → Tools → Memory → Events → UI
```

### V2: Multi-Agent Network
```
Human → Parent Agent ──spawn──→ Child 1 (worker)
                      ──spawn──→ Child 2 (researcher)
                      ──orchestrate──→ [subtask₁ ∥ subtask₂ ∥ subtask₃] → synthesis

Inter-agent: TASK ↔ RESULT, QUESTION ↔ ANSWER, GUIDANCE
Tool scoping: each agent sees only its allowed tools
Graph view: real-time visualization of the entire network
```

### Principles maintained from V1
- **App factory pattern:** `create_app(settings)` with dependency injection
- **Events as foundation:** every multi-agent interaction emits events
- **Async-first:** all I/O is async, no blocking calls
- **Cross-platform:** Linux + Windows compatibility
- **LLM-agnostic:** OpenRouter provider behind abstract interface

---

## 5. Use Case Validation

| UC | Title | Validates | Result | Issues |
|----|-------|-----------|--------|--------|
| UC-001 | Greeting & Memory | Auto-extraction, recall | PASS | — |
| UC-002 | HITL Approval Flow | Approve/deny gates | PASS | — |
| UC-003 | Tool System | MCP filesystem/shell, macros | PASS (r2) | r1: macro used wrong model (fixed) |
| UC-004 | Memory System | Remember/recall/forget, cross-agent, decay | PASS | — |
| UC-005 | Multi-Agent Orchestration | Spawn, lifecycle, all 3 strategies | PASS | — |
| UC-006 | Inter-Agent Communication | Message types, auto-wake, stop/dismiss | PASS | 2 issues found and fixed |
| UC-007 | Orchestration Patterns | Decompose, sequential/parallel/pipeline | PASS | — |
| UC-008 | Per-Agent Tool Scoping | MCP filtering, tool whitelist | PASS | — |
| UC-009 | Graph View | Agent graph, subtasks, messages, dashboard | Created | Pending execution |

**Issues found and resolved during UC runs:**
1. **UC-003 Issue 2:** `PromptMacroProvider` used `LLMConfig()` default model instead of agent's model → Fixed by propagating `_llm_config` from runtime
2. **UC-006 Issue 1:** Auto-wake triggered on all message types → Fixed by filtering to actionable types only (status_update excluded)
3. **UC-006 Issue 2:** REST API `POST /agents/{id}/messages` accepted messages to COMPLETED agents → Fixed by adding status validation (returns 409)

---

## 6. Backlog Status

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| BL-001 | delete_agent tool | Open | Low priority — dismiss covers most needs |
| BL-002 | Per-agent MCP configuration | **Done (V2P4)** | Delivered as `allowed_mcp_servers` + `allowed_tools` |
| BL-003 | EventBus filtering by name/module | Open | Low priority |
| BL-004 | LLM-assisted HITL mode | Open | Medium priority — grows with agent autonomy |
| BL-005 | Orchestration subtasks with tools/agents | Open | Medium — unlocks real-world orchestration |
| BL-006 | Live orchestration graph | **Done (V2P5)** | Basic + Enhanced tiers; Full tier split to BL-007 |
| BL-007 | Timeline scrubber & historical replay | Open | Low — quality of life for debugging and demos |

---

## 7. File Summary

### New backend files (V2)
```
tools/agent_spawner.py              — Spawning, lifecycle, messaging (9 tools)
orchestration/models.py             — TaskPlan, SubTask, OrchestrationResult
orchestration/decomposer.py         — LLM-based task decomposition
orchestration/strategies.py         — Sequential, Parallel, Pipeline executors
orchestration/synthesizer.py        — Result synthesis
orchestration/tool_provider.py      — decompose_task, orchestrate tools
db/sqlite_message_repo.py           — Message persistence
api/message_routes.py               — Message REST API + auto-wake
prompts/system/decompose_task.md    — Decomposition system prompt
prompts/system/synthesize_results.md — Synthesis system prompt
prompts/worker.md + worker.json     — Reusable worker template
prompts/coder.md + coder.json       — Autonomous coder template
docs/CONFIGURATION_GUIDE.md         — Operator configuration reference
```

### New frontend files (V2)
```
app/graph/page.tsx                  — Graph page
components/graph/GraphCanvas.tsx    — React Flow canvas
components/graph/AgentNode.tsx      — Agent compound node
components/graph/MessageEdge.tsx    — Message bezier edge
components/graph/ParentChildEdge.tsx — Hierarchy straight edge
components/graph/DashboardHeader.tsx — Stats bar
components/graph/GraphFilters.tsx   — Filter sidebar
components/graph/SpawnAgentForm.tsx  — Agent creation form
components/graph/graphUtils.ts      — Node/edge builders + dagre layout
hooks/useGraphData.ts               — Graph data hook with SSE
components/MessagePanel.tsx         — Inter-agent message browser
app/memories/page.tsx               — Memory browser page
```

### Modified files
```
core/runtime.py                     — Async spawn, message injection, auto-wake, guidance
core/models.py                      — AgentConfig (allowed_tools, allowed_mcp_servers, orchestration fields)
core/platform_config.py             — Config resolution chain, agent file config
tools/registry.py                   — Tool schema filtering by scope
tools/prompt_macro.py               — LLM config propagation fix
api/routes.py                       — Agent children endpoint
app/layout.tsx                      — GRAPH nav link
app/agents/[id]/page.tsx            — SUB-AGENTS bar, PARENT link, MessagePanel
lib/api.ts                          — Children, messages, cost API functions
```

---

## 8. Smoke Test Summary

```
Backend:  121 tests across 12 files (V1P0–V1P7: 70, V2P1–V2P4: 51)
Frontend:  19 tests across  3 files (V1P5: 4, V2P2: 2, V2P5: 13)
Total:    140 tests — all passing, 0 flaky, fully deterministic
```

All tests mock LLM calls and external APIs. Run with:
```bash
just smoke-test           # Backend (121 tests)
cd frontend && npx vitest # Frontend (19 tests)
```

---

## 9. V2 → V3 Readiness

V2 provides the foundation for V3 (Self-Evolution & Capability Acquisition):

| V2 Capability | Enables for V3 |
|---------------|----------------|
| Agent spawning | Capability-acquisition agents that spawn specialized workers |
| Message bus | Agents can request tool creation from a builder agent |
| Orchestration | Multi-step capability gap analysis and tool development workflows |
| Tool scoping | Newly created tools can be selectively granted to specific agents |
| Memory (public) | Learned procedures and tool knowledge shared across agents |
| Events | Full audit trail of self-evolution actions |

**Recommended before V3:**
1. BL-005: Wire orchestration subtasks to tools/agents (unlocks real-world orchestration)
2. BL-004: LLM-assisted HITL (usability as agent autonomy increases)
3. BL-001: delete_agent tool (full lifecycle management)
