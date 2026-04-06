# Post-V4 Report — Self-Evolving Multi-Agent Platform

> **Date:** 2026-04-06
> **Status:** V4 Complete (3 phases, 192 smoke tests passing)
> **Author:** Claude Code (implementation) / Radek Zitek (direction)

---

## 1. Executive Summary

V4 is **complete and functional**. The platform has evolved from V3's skills and MCP management system into a fully searchable knowledge platform with RAG-based document ingestion, recursive knowledge scanning, and unified capability discovery. Post-V4 work added agent time/date awareness via dual mechanisms (system prompt injection + tool).

**Key numbers:**
- 192 smoke tests passing (all phases V1–V4)
- 3 V4 phases delivered
- 0 regressions against V1–V3 test suites

---

## 2. Phase Completion Status

| Phase | Title | Status | Tests |
|-------|-------|--------|-------|
| V4P1 | Technical Cleanup | Complete | 9/9 |
| V4P2 | RAG Knowledge Base | Complete | 9/9 |
| V4P3 | Unified Capability Discovery | Complete | 6/6 |
| **V1–V3 (maintained)** | **All prior phases** | **Passing** | **168/168** |
| **Total** | | | **192** |

---

## 3. What Was Built

### 3.1 V4 Phase 1 — Technical Cleanup

Addressed accumulated technical debt from V1–V3.

### 3.2 V4 Phase 2 — RAG Knowledge Base

Markdown-based knowledge ingestion with embedding search via ChromaDB.

**Components:**
- `KnowledgeStore` — ingests `.md` files, chunks by heading, embeds via OpenRouter, stores in ChromaDB
- `chunk_markdown()` — splits documents by heading hierarchy with configurable max chunk size
- Content-hash deduplication — skips re-embedding unchanged files

**Tools added:** `search_knowledge`, `ingest_document`

**Key decisions:**
- Chunks preserve heading paths (e.g., "Parent > Child") for context
- SHA-256 content hashing avoids redundant embedding API calls
- `README*.md` files are excluded from ingestion

### 3.3 V4 Phase 3 — Unified Capability Discovery

Single `discover_capabilities` tool that searches across all capability sources.

**Sources searched:** skills, agent templates, MCP tools, knowledge base

---

## 4. Post-V4 Enhancements

### 4.1 Recursive Knowledge Ingestion

**Problem:** Knowledge directory scanning only processed top-level `.md` files (`glob("*.md")`). Subdirectories were ignored, and symbolic links were not followed.

**Fix:** Changed `ingest_directory()` to use `glob("**/*.md", recurse_symlinks=True)`. This enables:
- Recursive scanning of nested directories (e.g., `knowledge/docs/phases/v1-phase-0/PLAN.md`)
- Following symbolic links (e.g., `knowledge/docs -> ../docs`)

**Source name collision fix:** Files were keyed by filename only (`path.name`), so files with identical names in different subdirectories (e.g., every phase has `PLAN.md`) would overwrite each other. Fixed by using relative paths as source keys (e.g., `docs/phases/v1-phase-0/PLAN.md`).

**Files changed:**
- `backend/src/agent_platform/knowledge/store.py` — `ingest()` accepts `base_dir` param, `ingest_directory()` uses recursive glob
- `backend/src/agent_platform/knowledge/chunker.py` — `chunk_markdown()` accepts `source_name` param

### 4.2 Agent Time & Date Awareness

**Problem:** Agents had no awareness of the current date or time. This limits their ability to reason about schedules, deadlines, recency, or time-sensitive tasks.

**Solution: Dual approach**

#### A. System Prompt Injection (passive awareness)

Every new conversation injects the current UTC date/time into the system prompt:

```
Current date and time: 2026-04-06 14:30:00 UTC (Sunday)
```

This gives agents baseline temporal awareness from the first message without requiring a tool call.

**File changed:** `backend/src/agent_platform/core/runtime.py` — appended to system prompt in conversation initialization

#### B. `get_current_time` Tool (active lookup)

For long-running conversations where the system prompt timestamp becomes stale, agents can call `get_current_time` to check the current time with optional timezone support.

**Parameters:**
- `timezone` (optional) — IANA timezone name (e.g., `Europe/Prague`, `America/New_York`). Defaults to UTC.

**Returns:** Formatted date/time string with day of week, e.g., `2026-04-06 16:30:00 CEST (Sunday)`

**Files added:** `backend/src/agent_platform/tools/datetime_provider.py`
**Files changed:** `backend/src/agent_platform/api/main.py` — registered `DateTimeToolProvider`

### 4.3 LLM Response Streaming

**Problem:** LLM responses were only visible in the conversation panel after the entire response completed. For long responses, the UI appeared frozen — the user had to wait for the full LLM output before seeing anything.

**Solution: End-to-end token streaming via existing SSE pipeline**

The platform already had SSE event streaming from backend to frontend. The fix threads token-level events through this existing infrastructure.

#### Backend: Streaming OpenRouter Provider

Modified `OpenRouterProvider.complete()` to use OpenRouter's streaming API (`stream: true`). As each token arrives:
1. Content delta is accumulated into the final response
2. An `LLM_TOKEN` event is emitted via the event bus with `{"token": "..."}` payload
3. Tool call deltas are accumulated and assembled into complete `ToolCall` objects

When streaming completes, the method returns the same `LLMResponse` as before — callers don't need to change.

Streaming is enabled by default but can be disabled via `stream=False` constructor parameter (used by tests with mock transports).

**Files changed:**
- `backend/src/agent_platform/llm/openrouter.py` — added `_stream_request()` and `_blocking_request()` methods, `stream` constructor param
- `backend/src/agent_platform/observation/events.py` — added `LLM_TOKEN` event type

#### Frontend: Live Token Display

The agent page accumulates `llm_token` events into a streaming content buffer displayed as a live assistant message with a blinking cursor. Token events are excluded from the event timeline to avoid noise.

The streaming bubble is cleared on `llm_request` (new turn) and `llm_response` (turn complete, real message loaded from conversation).

**Files changed:**
- `frontend/src/app/agents/[id]/page.tsx` — streaming state, token accumulation, clear on response
- `frontend/src/components/AgentDetail.tsx` — `ConversationPanel` accepts `streamingContent` prop, renders live bubble

### 4.4 Agent Loop — Scheduled Periodic Wake-Ups

**Problem:** The platform had no mechanism for long-running agents. Once an agent completed its turn, it went IDLE with no way to wake itself up on a schedule. Use cases like email monitoring, polling external services, or periodic health checks were impossible.

**Solution: `agent_loop` tool + background scheduler**

Agents can now set up their own periodic wake-up calls using the `agent_loop` tool. A background scheduler checks the registry every second and sends TASK messages to due agents, leveraging the existing auto-wake infrastructure.

#### `agent_loop` Tool

**Actions:**
- `start(interval, message)` — Register periodic wake-ups. The agent receives a TASK message with the given content every `interval` seconds. Minimum interval: 10 seconds (guard against self-DOS).
- `stop()` — Cancel the loop. The agent can stop itself or be instructed to stop by a parent.
- `status()` — Check if a loop is active, its interval, and next wake time.

#### Architecture

```
Agent calls agent_loop(action="start", interval=60, message="Check email")
    |
    v
LoopRegistry stores: {agent_id -> (interval=60, message, next_wake)}
    |
    v
Background scheduler (asyncio task, 1s tick)
    |-- checks registry for due entries
    |-- creates TASK AgentMessage from "scheduler"
    |-- calls wake_idle_agent() (existing auto-wake)
    |-- advances next_wake by interval
    |
    v
Agent wakes, runs turn, goes IDLE, waits for next wake
```

**Key design decisions:**
- Agents control their own scheduling (self-service, not config-driven)
- Agents can dynamically adjust interval (call `start` again with new value)
- If agent is busy (not IDLE) when tick fires, the tick is skipped — no queuing
- If agent is deleted or not found, loop auto-unregisters
- Registry is in-memory (resets on server restart — loops need to be re-established)
- Scheduler sends messages via the existing `send_message` / `wake_idle_agent` path — no new wake mechanism

**Example use case — email monitoring:**
1. Parent spawns `email_monitor` with system prompt: "Check for new emails and report"
2. Parent sends TASK: "Monitor my email every 60 seconds"
3. Agent checks email via Gmail MCP tools, reports results to parent via `send_message`
4. Agent calls `agent_loop(action="start", interval=60, message="Check for new email")`
5. Agent goes IDLE
6. Every 60s, scheduler wakes agent; agent checks email, reports if new, goes IDLE again
7. Parent sends "stop monitoring" -> agent calls `agent_loop(action="stop")`

**Files added:** `backend/src/agent_platform/tools/agent_loop.py` (LoopRegistry, AgentLoopProvider, loop_scheduler)
**Files changed:** `backend/src/agent_platform/api/main.py` — registered provider, started scheduler in lifespan

### 4.5 Live Config Reload

**Problem:** Agent config and system prompt were baked in at creation time. If prompt files were updated on disk (e.g., new tool documentation added to `default.md`), existing agents would never see the changes. The only option was to delete and recreate the agent, losing its conversation history and memories.

**Solution: `POST /agents/{agent_id}/reload-config` endpoint + UI button**

#### API Endpoint

`POST /agents/{agent_id}/reload-config` re-resolves the agent's config from source files:

1. Reads `{prompts_dir}/{agent_name}.md` for system prompt (falls back to `default.md`)
2. Reads `{prompts_dir}/{agent_name}.json` for config overrides (falls back to `default.json`)
3. Applies platform defaults from `lyra.config.json`
4. Updates the agent record in the database
5. Patches the first SYSTEM message in the conversation so the agent sees the new prompt on its next turn

Returns `{ prompt_changed, model_changed, conversation_updated }` so the caller knows what changed.

#### Frontend

A **RELOAD CONFIG** button is always visible in the agent detail header (blue styling, next to RESET). Clicking it calls the reload endpoint and refreshes the page.

#### Refactoring

Extracted config resolution logic from `create_agent` into a shared `_resolve_config_from_files(template_name)` helper used by both creation and reload. This eliminates the duplicated 80+ lines of resolution code.

**Files changed:**
- `backend/src/agent_platform/api/routes.py` — extracted `_resolve_config_from_files()`, added `reload_agent_config` endpoint
- `frontend/src/lib/api.ts` — added `reloadAgentConfig()` function
- `frontend/src/app/agents/[id]/page.tsx` — added RELOAD CONFIG button

---

## 5. Current Architecture

### Tool Providers Registered (in order)

| # | Provider | Tools | Source |
|---|----------|-------|--------|
| 1 | MemoryToolProvider | remember, recall, forget | memory |
| 2 | SkillProvider | dynamic (from `skills/*.md`) | skill |
| 3 | TemplateProvider | create_from_template, list_templates | template |
| 4 | McpServerManager | dynamic (from MCP servers) | mcp |
| 5 | AgentSpawner | spawn_agent, wait_for_agent, etc. | agent |
| 6 | OrchestrationProvider | decompose_task, orchestrate | orchestration |
| 7 | KnowledgeToolProvider | search_knowledge, ingest_document | knowledge |
| 8 | DiscoveryProvider | discover_capabilities | discovery |
| 9 | DateTimeToolProvider | get_current_time | datetime |
| 10 | **AgentLoopProvider** | **agent_loop** | **agent_loop** |
| 11 | CapabilityToolProvider | analyze, reflect, analytics, patterns | capability |
