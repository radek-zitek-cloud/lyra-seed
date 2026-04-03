# Project Roadmap — Self-Evolving Multi-Agent Platform

> **Status:** Draft v1 — Brainstorming Output
> **Author:** Radek Zítek / zitek.cloud
> **Last Updated:** 2026-04-01

---

## 1. Project Overview

An experimental platform for orchestrating self-evolving LLM-powered agents. A single-human dedicated assistant system where agents can consume and create tools, delegate to sub-agents, communicate across agent boundaries, and learn from experience through layered memory. The platform emphasizes extreme observability and human-in-the-loop control.

### Core Principles

- **Abstraction-first:** Every major subsystem (LLM provider, database, memory strategy, tool interface) is fronted by an abstract interface with a simple initial implementation. This enables future swap-out without rewrites.
- **Observability as foundation:** The event system is built in Phase 1 and everything flows through it. It is never retrofitted.
- **Cross-platform:** All tooling, scripts, and runtime must work on both Linux (bash) and Windows (PowerShell).
- **Single-user model:** The system serves one human. There is no multi-tenancy in scope.

---

## 2. Tech Stack

| Layer              | Technology                          | Notes                                              |
|--------------------|-------------------------------------|----------------------------------------------------|
| **Backend**        | Python, FastAPI, Pydantic           | Async-first. Pydantic for all data contracts.      |
| **Frontend**       | TypeScript, React, Next.js          | Observation UI and HITL interface.                  |
| **Database**       | SQLite (initial)                    | Behind a repository abstraction layer.             |
| **Vector Storage** | SQLite + sqlite-vec (initial)       | Behind embedding store abstraction.                |
| **LLM Provider**   | OpenRouter (initial)                | Behind abstract provider interface.                |
| **Embeddings**     | openai/text-embedding-3-large      | Via OpenRouter. Behind abstract embedder interface.|
| **Build Tool**     | uv                                 | Python dependency management and packaging.        |
| **Task Runner**    | justfile                            | Cross-platform recipes (bash + PowerShell).        |
| **Deployment**     | Local dev → Docker                 | Dockerized deployment as maturity target.          |

---

## 3. Architecture Overview

### 3.1 Subsystems

```
┌─────────────────────────────────────────────────────────────────┐
│                      Observation UI (Next.js)                   │
│  Timeline │ Agent Graph │ Message Flow │ Tool Inspector │ HITL  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket + REST
┌──────────────────────────┴──────────────────────────────────────┐
│                      API Gateway (FastAPI)                      │
├─────────────┬──────────────┬──────────────┬─────────────────────┤
│ Agent       │ Tool         │ Orchestration│ Observation         │
│ Runtime     │ System       │ & Comms      │ & Events            │
├─────────────┼──────────────┼──────────────┼─────────────────────┤
│ Memory System (Context │ Cross-Context │ Long-Term)             │
├─────────────────────────────────────────────────────────────────┤
│ Abstraction Layer (LLM Provider │ DB │ Embeddings │ Strategy)   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Core Abstractions

Each of these is defined as a Python abstract base class (or Protocol) with one concrete implementation at V1 launch:

| Abstraction             | Initial Implementation         | Future Options                    |
|-------------------------|--------------------------------|-----------------------------------|
| `LLMProvider`           | OpenRouter (HTTP)              | Anthropic direct, Ollama, etc.    |
| `EmbeddingProvider`     | OpenRouter (text-embedding-3-large) | Local sentence-transformers  |
| `Repository` (DB)       | SQLite via aiosqlite           | PostgreSQL, etc.                  |
| `VectorStore`           | sqlite-vec                     | pgvector, Qdrant, ChromaDB       |
| `MemoryStrategy`        | Time-decay                     | Relevance-decay, hybrid, LRU     |
| `ToolProvider`          | MCP client                     | Custom function registry          |
| `EventBus`              | In-process async (+ SQLite log)| Redis Streams, NATS, etc.         |

### 3.3 Agent Core Loop

```
Human Prompt
    │
    ▼
┌──────────┐    ┌───────────┐
│ Context  │───▶│ LLM Call  │
│ Assembly │    │ (Provider)│
└──────────┘    └─────┬─────┘
                      │
              ┌───────┴────────┐
              │ Response Parse │
              └───────┬────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    ┌─────────┐ ┌──────────┐ ┌─────────┐
    │ Tool    │ │ Subagent │ │ Final   │
    │ Call    │ │ Spawn    │ │ Response│
    └────┬────┘ └────┬─────┘ └────┬────┘
         │           │            │
         └───────────┴────────────┘
                      │
              ┌───────┴────────┐
              │ Memory Write   │
              │ Event Emit     │
              └────────────────┘
```

---

## 4. V1 — MVP: Single Agent with Observability & Memory

**Goal:** A single agent that can converse with the human, call tools (MCP + prompt macros), remember across sessions, and expose its full execution trace in a web UI.

---

### V1 Phase 0: Project Skeleton & Tooling

**Objective:** Establish repository structure, build tooling, cross-platform justfile, and CI-ready project layout.

**Deliverables:**

- Monorepo structure:
  ```
  /
  ├── backend/          # FastAPI app (Python, uv-managed)
  │   ├── src/
  │   │   └── agent_platform/
  │   │       ├── core/           # Agent runtime, event bus
  │   │       ├── llm/            # LLM provider abstraction + OpenRouter impl
  │   │       ├── memory/         # Memory abstractions + implementations
  │   │       ├── tools/          # Tool interface, MCP client, prompt macros
  │   │       ├── orchestration/  # (V2) Sub-agent spawning, comms
  │   │       ├── observation/    # Event models, query API
  │   │       ├── db/             # Repository abstraction + SQLite impl
  │   │       └── api/            # FastAPI routes, WebSocket endpoints
  │   ├── tests/
  │   ├── pyproject.toml
  │   └── uv.lock
  ├── frontend/         # Next.js observation UI
  │   ├── src/
  │   ├── package.json
  │   └── tsconfig.json
  ├── justfile          # Cross-platform task recipes
  ├── .env.example
  ├── ROADMAP.md
  └── README.md
  ```
- `justfile` with recipes for:
  - `just dev-backend` / `just dev-frontend` / `just dev` (both)
  - `just test` / `just lint` / `just format`
  - `just db-migrate` / `just db-reset`
  - All recipes tested on Linux bash and Windows PowerShell
- Pydantic settings model for configuration (env-based)
- Basic health-check endpoint in FastAPI
- uv project initialization with dev dependency groups
- Git repository with `.gitignore`, pre-commit hooks (ruff, mypy)

**Exit Criteria:** `just dev` starts both backend and frontend on a fresh clone on both Linux and Windows.

---

### V1 Phase 1: Abstractions & Event System

**Objective:** Build the foundational abstract interfaces and the event system that everything will flow through.

**Deliverables:**

**1.1 — Core Abstractions (Python Protocols / ABCs)**

- `LLMProvider` protocol:
  - `async def complete(messages, tools?, config?) -> LLMResponse`
  - `LLMResponse` model: content, tool_calls, usage metadata, raw_response
- `EmbeddingProvider` protocol:
  - `async def embed(texts: list[str]) -> list[list[float]]`
  - `async def embed_query(text: str) -> list[float]`
- `Repository[T]` generic protocol:
  - `async def get(id) -> T | None`
  - `async def list(filters?, pagination?) -> list[T]`
  - `async def create(entity: T) -> T`
  - `async def update(id, entity: T) -> T`
  - `async def delete(id) -> bool`
- `VectorStore` protocol:
  - `async def store(id, vector, metadata) -> None`
  - `async def search(query_vector, top_k, filters?) -> list[VectorResult]`
  - `async def delete(id) -> bool`
- `Strategy[TInput, TOutput]` generic protocol (reusable pattern):
  - `async def execute(input: TInput) -> TOutput`
  - Used for memory decay, context compression, task decomposition, etc.

**1.2 — Event System**

- `Event` base Pydantic model:
  - `id: UUID`
  - `timestamp: datetime`
  - `agent_id: str`
  - `event_type: EventType` (enum: LLM_REQUEST, LLM_RESPONSE, TOOL_CALL, TOOL_RESULT, MEMORY_READ, MEMORY_WRITE, AGENT_SPAWN, AGENT_COMPLETE, HITL_REQUEST, HITL_RESPONSE, MESSAGE_SENT, MESSAGE_RECEIVED, ERROR)
  - `parent_event_id: UUID | None` (for grouping/nesting)
  - `module: str` (logical grouping — e.g., "memory", "tools.mcp", "llm.openrouter")
  - `payload: dict` (event-type-specific data)
  - `duration_ms: int | None`
- `EventBus` protocol:
  - `async def emit(event: Event) -> None`
  - `async def subscribe(event_types?, agent_id?) -> AsyncIterator[Event]`
  - `async def query(filters: EventFilter) -> list[Event]`
- Initial implementation: `InProcessEventBus`
  - In-memory async queue for real-time subscribers (WebSocket feed)
  - Append-only write to SQLite `events` table for persistence and query
- EventFilter model for querying:
  - By agent_id, event_type, time range, module, parent_event_id

**Exit Criteria:** Events can be emitted, persisted to SQLite, queried back, and streamed to a subscriber. Full test coverage for the event bus.

---

### V1 Phase 2: Agent Runtime

**Objective:** Implement the core agent loop — the agent can receive a prompt, call the LLM, handle tool calls in a loop, and return a response. Everything emits events.

**Deliverables:**

**2.1 — Agent Data Model**

- `Agent` Pydantic model:
  - `id: str` (UUID)
  - `name: str`
  - `status: AgentStatus` (IDLE, RUNNING, WAITING_HITL, COMPLETED, FAILED)
  - `config: AgentConfig` (LLM model, temperature, max_iterations, system_prompt, allowed_tools)
  - `parent_agent_id: str | None`
  - `created_at, updated_at: datetime`
- `Conversation` model:
  - `id: str`
  - `agent_id: str`
  - `messages: list[Message]`
- `Message` model:
  - `role: MessageRole` (HUMAN, ASSISTANT, SYSTEM, TOOL_RESULT)
  - `content: str | list[ContentBlock]`
  - `tool_calls: list[ToolCall] | None`
  - `timestamp: datetime`
- SQLite repository implementations for Agent and Conversation

**2.2 — Agent Runtime Engine**

- `AgentRuntime` class:
  - `async def run(agent_id, human_message) -> AgentResponse`
  - Core loop:
    1. Load agent config and conversation history
    2. Assemble context (system prompt + history + memory retrieval)
    3. Call `LLMProvider.complete()`
    4. If response contains tool calls → execute tools → append results → go to step 3
    5. If response is final text → emit events, write memory, return
  - Configurable `max_iterations` to prevent infinite tool loops
  - Every step emits events via EventBus
- `OpenRouterProvider` implementation of `LLMProvider`:
  - HTTP client (httpx async) to OpenRouter API
  - Request/response mapping to/from internal models
  - Error handling, retries with exponential backoff
  - Usage tracking (tokens, cost) in event payload

**2.3 — HITL Foundation**

- Permission gate mechanism:
  - Agent config defines `hitl_policy: HITLPolicy` (ALWAYS_ASK, DANGEROUS_ONLY, NEVER)
  - When a tool call requires approval, agent status → WAITING_HITL
  - Emits HITL_REQUEST event with the pending action
  - Runtime pauses (async wait) until HITL_RESPONSE event is received
- API endpoint: `POST /agents/{id}/hitl-respond` (approve/deny with optional message)

**Exit Criteria:** An agent can be created, receive a prompt, call the LLM via OpenRouter, and return a response. The full execution trace is visible in the events table. HITL gates block execution until the human responds.

---

### V1 Phase 3: Tool System

**Objective:** The agent can invoke tools — both MCP server tools and local prompt macros. Tool calls flow through the event system.

**Deliverables:**

**3.1 — Tool Interface**

- `Tool` model:
  - `name: str`
  - `description: str`
  - `input_schema: dict` (JSON Schema)
  - `tool_type: ToolType` (MCP, PROMPT_MACRO)
  - `source: str` (MCP server URL, or macro ID)
- `ToolProvider` protocol:
  - `async def list_tools() -> list[Tool]`
  - `async def call_tool(name, arguments) -> ToolResult`
- `ToolResult` model:
  - `success: bool`
  - `output: str | dict`
  - `error: str | None`
  - `duration_ms: int`
- `ToolRegistry`:
  - Aggregates tools from multiple providers
  - Resolves tool names to providers
  - Provides the combined tool list for LLM context

**3.2 — MCP Client**

- Implement `MCPToolProvider`:
  - Connects to MCP servers via stdio or HTTP/SSE transport
  - Discovers available tools from the server
  - Forwards tool calls and returns results
  - Connection lifecycle management
- MCP server configuration in agent config or global settings
- Event emission for every MCP interaction (connect, list, call, result)

**3.3 — Prompt Macros**

- `PromptMacro` model:
  - `id: str`
  - `name: str`
  - `description: str`
  - `template: str` (with `{{parameter}}` placeholders)
  - `parameters: dict` (JSON Schema for the parameters)
  - `output_instructions: str` (how to format/parse the LLM's response)
- `PromptMacroProvider` implementing `ToolProvider`:
  - Expands the template with provided arguments
  - Sends the expanded prompt to the LLM as a sub-call
  - Returns the result as a ToolResult
- CRUD API for managing prompt macros
- Stored in SQLite via repository abstraction

**Exit Criteria:** Agent can discover and call MCP tools and prompt macros in its tool loop. All tool interactions appear as events. Human can manage prompt macros via API.

---

### V1 Phase 4: Memory System

**Objective:** Three-tier memory — context, cross-context (autobiographical), and long-term (factual/procedural). Agent can remember and recall across sessions.

**Deliverables:**

**4.1 — Context Memory Manager**

- `ContextManager`:
  - Assembles the message list for the LLM call
  - Monitors token budget (estimated via tiktoken or similar)
  - `ContextCompression` strategy (abstraction):
    - Initial implementation: truncation with summary (oldest messages get summarized)
    - Interface allows future swap to more sophisticated strategies
  - Injects relevant memories from cross-context and long-term stores

**4.2 — Cross-Context Semantic Memory (Autobiographical)**

- What it stores: summaries of agent sessions, key decisions made, user preferences observed, outcomes of tasks
- `MemoryEntry` model:
  - `id: str`
  - `agent_id: str`
  - `content: str` (the memory text)
  - `embedding: list[float]`
  - `memory_type: MemoryType` (EPISODIC, PREFERENCE, DECISION, OUTCOME)
  - `importance: float` (0.0–1.0, affects retrieval ranking)
  - `created_at: datetime`
  - `last_accessed_at: datetime`
  - `access_count: int`
  - `decay_score: float` (computed by strategy)
- Memory write triggers:
  - End of each agent run: auto-generate a session summary
  - Explicit agent action: agent calls a "remember" tool
  - HITL: human can annotate with "remember this"
- Memory retrieval:
  - Semantic search via VectorStore (embed query → similarity search)
  - Filtered by memory_type, recency, importance
  - Top-K results injected into context

**4.3 — Long-Term Semantic Memory (Factual/Procedural)**

- What it stores: learned facts, domain knowledge, how-to procedures, tool documentation
- Same `MemoryEntry` model but with `memory_type` values: FACT, PROCEDURE, TOOL_KNOWLEDGE, DOMAIN_KNOWLEDGE
- Write triggers:
  - Agent explicitly stores knowledge ("I learned that...")
  - After successful tool creation (V3): store the tool's purpose and usage
  - Human teaches the agent via HITL
- Retrieval: same semantic search mechanism, possibly with boosted importance scores

**4.4 — Memory Strategy Framework**

- `MemoryDecayStrategy` (implements `Strategy[MemoryEntry, float]`):
  - Input: a memory entry
  - Output: updated decay_score (0.0 = should be forgotten, 1.0 = fully retained)
  - Initial implementation: `TimeDecayStrategy`
    - Score decreases logarithmically with time since last access
    - Boosted by access_count and importance
    - Configurable half-life parameter
  - Memory garbage collection:
    - Background task runs periodically
    - Entries below decay threshold are archived or deleted
    - Events emitted for all GC actions
- `ContextCompressionStrategy` (implements `Strategy[list[Message], list[Message]]`):
  - Initial implementation: `TruncateAndSummarize`
    - Keeps last N messages verbatim
    - Summarizes older messages into a condensed block
    - Uses LLM to generate summaries

**4.5 — Memory as Tools**

- Expose memory operations as tools the agent can invoke:
  - `remember(content, memory_type, importance)` — store a memory
  - `recall(query, memory_type?, top_k?)` — retrieve relevant memories
  - `forget(memory_id)` — explicitly delete a memory
- This allows the agent to *decide* when to remember/recall, making memory usage part of its reasoning

**4.6 — Embedding Infrastructure**

- `OpenRouterEmbeddingProvider` implementing `EmbeddingProvider`:
  - Calls OpenRouter with model `openai/text-embedding-3-large`
  - Batching support for bulk embedding operations
  - Caching layer (don't re-embed identical text)
- `SqliteVectorStore` implementing `VectorStore`:
  - Uses sqlite-vec extension for vector similarity search
  - Stores vectors alongside metadata
  - Supports filtered search (by memory_type, agent_id, etc.)

**Exit Criteria:** Agent retrieves relevant memories at the start of each run. Agent can explicitly remember/recall via tools. Memories persist across sessions. Decay strategy runs and prunes stale memories. All memory operations appear as events.

---

### V1 Phase 5: Observation UI

**Objective:** A web-based dashboard where the human can observe agent execution in real-time and interact via HITL controls.

**Deliverables:**

**5.1 — Backend API for Observation**

- REST endpoints:
  - `GET /agents` — list all agents
  - `GET /agents/{id}` — agent details and status
  - `GET /agents/{id}/events` — query events with filters (type, time range, module)
  - `GET /agents/{id}/conversations` — conversation history
  - `GET /tools` — list all registered tools
  - `GET /tools/{name}/calls` — history of calls to a specific tool
  - `POST /agents` — create/spawn a new agent
  - `POST /agents/{id}/prompt` — send a human message to the agent
  - `POST /agents/{id}/hitl-respond` — approve/deny a HITL gate
- WebSocket endpoint:
  - `WS /agents/{id}/events/stream` — real-time event stream for an agent
  - `WS /events/stream` — global event stream (all agents)

**5.2 — Observation UI: Agent View**

- Agent detail page:
  - Header: agent name, status badge, config summary
  - Conversation panel: chat-style view of human ↔ agent messages
  - Event timeline: chronological list of all events, filterable by type and module
    - Each event expandable to show full payload
    - Color-coded by event type
    - Nested events (parent/child) shown with indentation
  - Input bar: send a new prompt to the agent

**5.3 — Observation UI: Tool Inspector**

- Tool calls panel (within agent view or standalone):
  - List of all tool invocations with timestamp, tool name, duration
  - Expandable to show input arguments and output
  - Status indicator (success/failure)
  - Filter by tool name, status, time range

**5.4 — Observation UI: HITL Panel**

- Pending approvals queue:
  - Shows all WAITING_HITL actions across agents
  - For each: what the agent wants to do, why, risk level
  - Approve / Deny buttons with optional message field
- HITL history: log of past approvals/denials

**5.5 — Real-Time Updates**

- WebSocket integration in the frontend:
  - Event timeline updates live as events stream in
  - Agent status changes reflected immediately
  - HITL requests pop up as notifications
- Connection status indicator (connected/reconnecting)

**Exit Criteria:** Human can create an agent, send prompts, watch execution unfold in real-time, inspect tool calls, and approve/deny HITL gates — all in the browser.

---

## 5. V2 — Multi-Agent Orchestration

**Goal:** Agents can spawn sub-agents, delegate tasks, and communicate. The observation UI visualizes agent networks and message flow.

---

### V2 Phase 1: Sub-Agent Spawning & Lifecycle

**Deliverables:**

- `spawn_agent` tool available to agents:
  - Parameters: name, system_prompt, task_description, allowed_tools, hitl_policy
  - Creates a child agent with `parent_agent_id` set
  - Returns the child agent's ID
- Agent lifecycle management:
  - Parent can poll child status or await completion
  - Child completion emits AGENT_COMPLETE event to parent
  - Child failure handling: retry, escalate to parent, or escalate to human
- `wait_for_agent(agent_id)` tool: blocks parent until child completes
- `get_agent_result(agent_id)` tool: retrieves child's final output
- Lifecycle events: AGENT_SPAWN, AGENT_RUNNING, AGENT_COMPLETE, AGENT_FAILED
- Child agents inherit parent's memory access (read-only to parent's memories) unless configured otherwise

---

### V2 Phase 2: Inter-Agent Communication & Async Lifecycle

**Objective:** Enable parent-child agent communication, make sub-agent spawning asynchronous, and support long-lived reusable sub-agents.

**Background (from V2P1 testing):**

V2P1 proved that sub-agents can spawn and execute with full tool access. However, testing revealed critical limitations:

1. **Synchronous spawn blocks the parent.** `spawn_agent` blocks until the child completes all iterations (potentially minutes). The parent can't do anything else — no monitoring, no guidance, no parallel work.
2. **Sub-agents are one-shot throwaway.** Once a child completes its task and goes idle, there's no way to give it another task. A "coder" agent that built a project can't be reused to extend it — a fresh agent must be spawned.
3. **No mid-execution guidance.** If a child agent goes down the wrong path or needs clarification, the parent can't intervene. The only option is to wait for completion and then spawn a new child.
4. **Human can interact with idle children via UI** (navigating to the child agent and sending prompts), but the parent agent cannot.

**Deliverables:**

**2.1 — Asynchronous Sub-Agent Spawning**

- `spawn_agent` returns immediately with child agent ID (does not block)
- Child runs in a background asyncio task
- Parent continues its own tool loop after spawning
- New tools for lifecycle management:
  - `wait_for_agent(child_agent_id, timeout?)` — block until child completes or times out
  - `check_agent_status(child_agent_id)` — non-blocking status check
  - `stop_agent(child_agent_id)` — request graceful stop of a running child
- Background task cleanup on shutdown

**2.2 — Message Passing Protocol**

- `send_message(target_agent_id, content, message_type)` tool
- `receive_messages(since?, message_type?)` tool — checks inbox, non-blocking
- Message types: TASK, RESULT, QUESTION, ANSWER, GUIDANCE, STATUS_UPDATE
- `AgentMessage` model:
  - `id, from_agent_id, to_agent_id, content, message_type, timestamp, in_reply_to`
- Communication patterns:
  - Direct messaging (parent ↔ child, agent ↔ agent)
  - Parent broadcast (to all children)
  - Result aggregation (parent collects all child results)
- Communication events in the event stream: MESSAGE_SENT, MESSAGE_RECEIVED
- Message persistence in SQLite

**2.3 — Reusable Sub-Agent Lifecycle**

- Parent can send a TASK message to an idle child to give it a new assignment
- Child's `receive_messages` tool picks up the task and enters a new work cycle
- Child retains full conversation history and memory from previous tasks
- The agent lifecycle becomes: spawn → task 1 → idle → task 2 → idle → ... → eventual cleanup
- Parent decides when to reuse vs spawn fresh based on context
- New tool: `dismiss_agent(child_agent_id)` — marks child as COMPLETED (no longer reusable)

**2.4 — Message Inbox Integration in Runtime**

- At the start of each agent iteration, check for pending messages
- Inject new GUIDANCE/TASK messages into the conversation context
- This allows mid-execution course correction without waiting for completion

**2.5 — UI Updates**

- Agent detail page: message history panel showing inter-agent messages
- Parent agent view: sub-agent status with "send message" input
- Agent list: visual indicator for agents with unread messages

**Exit Criteria:** Parent can spawn a child async, send it multiple tasks over its lifetime, provide mid-execution guidance, and observe the full message flow in the UI. Child agents persist and accumulate context across tasks.

---

### V2 Phase 3: Orchestration Patterns — COMPLETE

**Deliverables:**

- Task decomposition tool:
  - Agent receives complex task → LLM breaks it into subtasks
  - Each subtask mapped to: existing tool, existing skill, or new sub-agent
  - Decomposition plan stored and tracked
- Orchestration strategies (Strategy pattern):
  - `SequentialOrchestration`: run subtasks one by one
  - `ParallelOrchestration`: run independent subtasks concurrently
  - `PipelineOrchestration`: output of one feeds into the next
- Result synthesis:
  - Parent agent collects all sub-agent results
  - Uses LLM to synthesize a unified response
- Failure handling strategy:
  - Retry, reassign, escalate, or skip — configurable per subtask

**Implementation notes:** Subtasks execute as direct LLM calls rather than tool calls or sub-agent spawns (see backlog BL-005). Added `orchestrationModel` and `maxSubtasks` config entries. Externalized decomposition and synthesis prompts to `prompts/system/`. System prompt updated to document orchestration tools.

---

### V2 Phase 4: Per-Agent Tool Scoping

**Objective:** Allow each agent to have its own tool set instead of sharing a single global tool registry. Reduces token overhead, enforces least-privilege access, and enables agent specialization.

**Background:** Currently all agents share one `ToolRegistry` containing every MCP server, memory tool, and spawner tool. Every LLM call sends the full 38+ tool schema regardless of what the agent actually needs. A filesystem worker pays the same token cost as a research agent. With orchestration patterns (V2P3) spawning more specialized sub-agents, this becomes a direct cost multiplier.

**Deliverables:**

- Per-agent `mcpServers` configuration in `prompts/{name}.json`:
  - Optional field — if omitted, inherits system-wide tools from `lyra.config.json`
  - If specified, agent gets only those MCP servers (plus core tools like memory, messaging)
  - Example: `{"mcpServers": ["filesystem"]}` — only filesystem tools, not shell
- Per-agent `ToolRegistry` instances:
  - Each `AgentRuntime.run()` builds a scoped registry for the agent
  - Core tools (memory, messaging, spawner) always included
  - MCP tools filtered by agent config
  - `allowed_tools` field in `AgentConfig` for explicit tool whitelist (already exists, needs enforcement)
- Tool schema optimization:
  - Only send relevant tool schemas to the LLM
  - Track token savings in cost events
- Spawned children inherit parent's tool scope unless template overrides it
- `docs/CONFIGURATION_GUIDE.md` — comprehensive configuration reference covering:
  - Environment variables (`.env`)
  - Platform config (`lyra.config.json`) — all fields, defaults, and purpose
  - Agent config files (`prompts/{name}.json`) — all fields, resolution chain, examples
  - Agent system prompts (`prompts/{name}.md`) — how they're resolved, what the default covers
  - Internal system prompts (`prompts/system/*.md`) — decomposition, synthesis, extraction, summarization
  - The four-level resolution chain: per-agent file → default file → platform config → hardcoded defaults
  - Example configurations for common agent roles (coder, researcher, restricted worker)

**Exit Criteria:** Different agents get different tool sets. A worker with `mcpServers: ["filesystem"]` does not see shell tools. Token usage per LLM call decreases proportionally to excluded tools. Configuration guide covers all config surfaces with examples.

---

### V2 Phase 5: Observation UI — Multi-Agent & Orchestration Graph

> **Important:** This phase adds a new **graph view** as a separate visualization alongside the existing event timeline and agent detail views. The current observation UI (event timeline, conversation panel, HITL panel, memory browser) is working well and must not be disrupted. The graph view is an additional perspective on the same data, not a replacement.

**Deliverables:**

- 5.1 Agent network graph:
  - Interactive node-edge visualization of parent-child agent relationships (React Flow)
  - Agent nodes as compound containers showing name, model, and status
  - Node color indicates status (idle/running/waiting/completed/failed)
  - Click node to drill into existing agent detail view
  - Real-time updates via SSE events
- 5.2 Orchestration subtask visualization (incorporates BL-006 Basic + Enhanced):
  - Orchestration subtask nodes rendered inside agent containers
  - Subtask status coloring (pending/running/completed/failed/skipped)
  - Dependency edges between subtasks within an agent (from plan's `dependencies` field)
  - Auto-synthesis shown as a final converging node
  - Pipeline progress visualization for pipeline-strategy orchestrations
- 5.3 Communication flow:
  - Inter-agent message edges with labels (message type, direction)
  - Filterable by agent pair, message type, time range
  - Spawn animations when new child agents appear
- 5.4 Dashboard & agent spawning:
  - Dashboard overview: active agents, statuses, recent events, aggregate metrics (total events, pending HITL, tool calls)
  - Spawn agent from UI: form to create a new root or child agent with config

**Tech:** React Flow with compound nodes, custom styling, animated edges, and Dagre/ELK auto-layout. All required data already streams via SSE — no backend changes needed for the graph view.

**Exit Criteria:** Graph view shows live agent hierarchy with orchestration subtasks updating in real-time. Existing event timeline and agent detail views unchanged. Dashboard shows aggregate platform state. Agents can be spawned from the UI.

---

### V2 Phase 6: Orchestration Subtasks with Tool & Agent Execution

> Promoted from BL-005. Prerequisite for V3 — the capability acquisition loop (V3P3) requires orchestrated subtasks to spawn agents and call tools, not just make standalone LLM calls.

**Deliverables:**

- `_execute_subtask()` branches on `subtask.assigned_to`:
  - `"spawn_agent"` — spawns a child agent with the subtask description as task, waits for result, extracts the agent's response as subtask output
  - Known tool name (matches a tool in `ToolRegistry`) — calls the tool directly via `tool_registry.call_tool()`, uses tool result as subtask output
  - Anything else (including `"llm"` or unknown) — falls back to current direct LLM call behavior
- Parallel strategy respects mixed subtask types (some LLM, some tool, some agent) running concurrently
- Pipeline strategy passes previous output as context regardless of subtask type
- Failure policies (retry, reassign, skip, escalate) work for all three execution modes
- Spawned sub-agents inherit parent's config (model, tool scoping) by default
- Concurrency guard: max parallel agent spawns configurable (default 5) to prevent resource exhaustion

**Exit Criteria:** An orchestrated task with `assigned_to: "spawn_agent"` subtasks spawns actual child agents, waits for their results, and synthesizes the output. Tool-assigned subtasks execute via the registry. Mixed plans (LLM + tool + agent subtasks) work in all three strategies. All existing orchestration smoke tests still pass.

---

### V2 Phase 7: Skills — Filesystem-Based Prompt Macros

**Objective:** Replace the database-backed prompt macro system with filesystem-based skill definitions. Skills are `.md` files with YAML frontmatter that define reusable LLM sub-call templates. Aligns with the project's filesystem-first configuration pattern and industry conventions (Claude Code commands, Cursor rules).

**Background:** The current `PromptMacroProvider` stores macros in SQLite via `SqliteMacroRepo` and manages them through CRUD API endpoints (`/macros`). In practice the feature is unused — no macros have been created outside of testing. Meanwhile, all other agent configuration (system prompts, agent configs, internal prompts) lives in the filesystem and works well. Moving macros to the filesystem as "skills" makes them discoverable, version-controlled, and editable without API calls.

**Deliverables:**

- Skill file format in `skills/` directory:
  ```markdown
  ---
  name: summarize
  description: Summarize text into bullet points
  parameters:
    text:
      type: string
      description: The text to summarize
      required: true
  ---

  Summarize the following text into 3-5 bullet points:

  {{text}}
  ```
  YAML frontmatter defines the tool schema (name, description, parameters). Body is the template with `{{parameter}}` placeholders.

- `SkillProvider` implementing `ToolProvider`:
  - Scans `skills/` directory for `.md` files at startup
  - Parses frontmatter + template from each file
  - Registers each skill as a tool in the `ToolRegistry`
  - Executes skills by expanding the template and making an LLM sub-call (same as current `PromptMacroProvider`)
  - Uses the calling agent's model (not LLMConfig default)

- Remove database-backed macro system:
  - Remove `SqliteMacroRepo` and its database table
  - Remove `macro_routes.py` (CRUD API)
  - Remove `PromptMacroProvider`
  - Remove macro loading from `main.py` lifespan

- Agent tool for runtime skill creation:
  - `create_skill(name, description, parameters, template)` tool
  - Writes a new `.md` file to `skills/` directory
  - Immediately available to all agents (re-scan or register on create)
  - Enables V3 self-evolution: agents can create new skills at runtime

- Configurable skills directory in `lyra.config.json`:
  - `"skillsDir": "./skills"` (default)
  - Documented in CONFIGURATION_GUIDE.md

- Bundled starter skills:
  - `summarize.md` — summarize text into bullet points
  - `translate.md` — translate text to a target language
  - `code-review.md` — review code for quality, bugs, and improvements

- Update documentation:
  - `prompts/README.md` — update to reference skills
  - `docs/CONFIGURATION_GUIDE.md` — add skills directory section
  - `prompts/default.md` — document skill tools in system prompt

**Exit Criteria:** Skills load from `skills/*.md` at startup and register as tools. Agents can call skills via function-calling. Agents can create new skills at runtime via `create_skill`. Database macro system fully removed. All existing smoke tests pass (macro-related tests updated or replaced).

---

## 6. V3 — Self-Evolution & Capability Acquisition

**Goal:** Agents can identify capability gaps and fill them by creating new tools. The system becomes self-improving.

---

### V3 Phase 1: Tool Creation — Skills — COMPLETE

**Deliverables:**

- Agent can create new skills dynamically (delivered in V2P7 via `create_skill` tool)
- Skill validation: `test_skill` dry-runs a template with test arguments, then evaluates the output against the skill's description via a second LLM call (execution model + evaluation with orchestration model). Returns PASS/FAIL verdict with reasoning.
- Skill versioning: `update_skill` renames the current file to `{name}.v{n}.md` and writes the new version. Version numbers auto-increment. Version files excluded from loading.
- Name validation: `create_skill` rejects invalid characters and reserved tool names.
- Semantic skill search: `list_skills(query="...")` embeds the query and ranks skills by cosine similarity to their descriptions.
- Skill deduplication: `create_skill` embeds the new description and rejects if similarity > 0.85 to an existing skill, preventing near-duplicate proliferation.
- Agent template discovery: `list_templates(query="...")` and `get_template(name)` tools let agents find the right template before spawning sub-agents. Same semantic search pattern as skills.
- Evaluation prompt externalized to `prompts/system/evaluate_skill.md`.
- All features degrade gracefully without an embedding provider.

---

### V3 Phase 2: Tool Creation — MCP Servers

**Deliverables:**

- Agent can scaffold a new MCP server:
  - `create_mcp_server(name, description, tools_spec)` tool
  - Generates Python code (FastMCP) or Node.js code (MCP SDK) based on spec
  - Writes to a managed directory
- MCP server lifecycle:
  - Build → Validate → Deploy (local process) → Register in tool registry
  - Health monitoring: event if server goes unhealthy
- Sandboxing considerations:
  - Created MCP servers run in isolated subprocess
  - Resource limits (memory, CPU, timeout)
  - Network access policy (configurable per server)
- Human approval gate: HITL required before deploying any agent-created MCP server

---

### V3 Phase 3: Capability Acquisition Loop

**Deliverables:**

- Capability gap analysis:
  - Agent receives task → checks available tools → identifies what's missing
  - `analyze_capabilities(task_description) -> CapabilityReport` tool
  - Report lists: available tools, missing capabilities, acquisition plan
- Acquisition sub-agent:
  - Specialized agent for building or finding new tools
  - Can search for existing MCP servers (registry/marketplace — if exists)
  - Can create prompt macros or MCP servers to fill gaps
  - Reports back to parent with new tool availability
- End-to-end "model case" flow:
  1. Human prompts with complex task
  2. Main agent decomposes task
  3. Identifies capability gaps
  4. Spawns acquisition sub-agent(s) for gaps
  5. Spawns execution sub-agent(s) for known subtasks
  6. Acquisition agents build/find tools → register them
  7. Main agent re-plans with new tools available
  8. Executes remaining subtasks
  9. Synthesizes final result

---

### V3 Phase 4: Learning & Knowledge Accumulation

**Deliverables:**

- Post-task reflection:
  - After completing a complex task, agent generates a retrospective
  - What worked, what failed, what tools were useful, what was missing
  - Stored in long-term memory as PROCEDURE knowledge
- Tool usage analytics:
  - Track which tools are used, success rates, average latency
  - Agent can query analytics to choose tools: "which tool works best for this?"
- Pattern library:
  - Successful task decomposition patterns stored as reusable templates
  - Agent can match new tasks against known patterns
- Memory management UI (roadmap from V1 discussion):
  - Human can browse all memories (cross-context and long-term)
  - Edit, delete, or boost importance of specific memories
  - Search memories semantically

---

## 7. Cross-Cutting Concerns

### 7.1 Testing Strategy

| Level          | Scope                              | Tools                           |
|----------------|------------------------------------|---------------------------------|
| Unit           | Individual functions, strategies   | pytest, pytest-asyncio          |
| Integration    | DB access, LLM calls, MCP client  | pytest + test fixtures, mocking |
| End-to-end     | Full agent run with tool calls     | pytest + httpx test client      |
| Frontend       | UI components, WebSocket behavior  | Vitest, React Testing Library   |

- LLM calls mocked in tests by default (deterministic responses)
- Optional integration test suite that hits real OpenRouter (gated by env var)
- Justfile recipes: `just test`, `just test-unit`, `just test-integration`, `just test-e2e`

### 7.2 Configuration Management

- All config via environment variables (12-factor)
- Pydantic `BaseSettings` model with `.env` file support
- Sensitive values (API keys) never logged or included in events
- Configuration scopes:
  - Global: LLM provider, database, embedding config
  - Per-agent: model, temperature, system prompt, HITL policy, allowed tools

### 7.3 Error Handling

- Structured error types inheriting from a base `AgentPlatformError`
- All errors emit ERROR events with full context
- LLM provider errors: retry with backoff, eventually surface to human
- Tool errors: captured as failed ToolResult, agent decides how to proceed
- Agent runtime errors: agent status → FAILED, human notified

### 7.4 Security Considerations

- API keys stored in environment, never in database
- Agent-created code (V3 MCP servers) runs sandboxed
- HITL gates on all destructive or external-facing actions
- No network access for agents by default (must be explicitly granted via tools)
- Rate limiting on LLM calls (configurable budget per agent)

### 7.5 Deployment

- **Development:** `just dev` starts everything locally
- **Docker:** docker-compose with backend + frontend + SQLite volume
- **Future:** Kubernetes manifests if scaling becomes relevant

### 7.6 Database Migrations

- Migration tool: Alembic (with async support)
- Justfile recipes: `just db-migrate`, `just db-rollback`, `just db-reset`
- Migrations versioned in repository
- sqlite-vec extension loaded at connection time

---

## 8. Milestone Summary

| Milestone | Description                              | Key Deliverable                              |
|-----------|------------------------------------------|----------------------------------------------|
| V1.0      | Project skeleton, tooling, CI            | `just dev` works cross-platform              |
| V1.1      | Abstractions, event system               | Events emitted, persisted, queryable         |
| V1.2      | Agent runtime, LLM integration           | Agent converses via OpenRouter               |
| V1.3      | Tool system (MCP + macros)               | Agent calls tools in its loop                |
| V1.4      | Memory system (3-tier)                   | Agent remembers across sessions              |
| V1.5      | Observation UI                           | Full web dashboard with real-time events     |
| V2.1      | Sub-agent spawning                       | Agent creates and manages children           |
| V2.2      | Inter-agent communication                | Agents exchange messages                     |
| V2.3      | Orchestration patterns                   | Task decomposition and delegation            |
| V2.4      | Per-agent tool scoping                   | Scoped tool registries, token optimization   |
| V2.5      | Multi-agent UI                           | Agent graph, message flow visualization      |
| V3.1      | Tool creation (macros)                   | Agent creates reusable prompt macros         |
| V3.2      | Tool creation (MCP servers)              | Agent scaffolds and deploys MCP servers      |
| V3.3      | Capability acquisition                   | Full gap-analysis → build → use loop         |
| V3.4      | Learning & knowledge                     | Retrospectives, analytics, pattern library   |

---

## 9. Open Questions & Future Considerations

- **Agent persistence model:** Should agents be long-lived (always available) or task-scoped (created per task, archived after)? V1 assumes long-lived, but this may evolve.
- **Concurrent agent execution:** V2 introduces parallelism. Need to decide on async concurrency model (asyncio tasks? process pool for CPU-bound MCP servers?).
- **Inter-agent trust:** When agents can create tools and delegate, should there be a trust/permission model between agents?
- **Cost tracking:** OpenRouter provides cost data. Should the platform track and budget LLM spending per agent?
- **Audit trail:** The event system provides a full audit trail. Should there be an immutable export/archive feature?
- **Plugin ecosystem:** Could third-party prompt macros or MCP server templates be shared/imported?
- **Multi-human:** Currently single-user. If this ever expands, what changes? (Auth, memory isolation, HITL routing.)

---

## Post-V1 Addendum

### V1 Completion Status

All six V1 phases (0–5) are **COMPLETE** with 45 smoke tests passing. The platform delivers a working single-agent system with observability, memory, tool calling, and a web UI.

### Technology Deviations

| Roadmap | Delivered | Rationale |
|---------|-----------|-----------|
| sqlite-vec for vector storage | ChromaDB (PersistentClient) | More mature, handles embeddings + metadata filtering natively, cross-platform |
| WebSocket for real-time events | SSE (Server-Sent Events) | WebSocket caused shutdown hangs on Windows/uvicorn; SSE has cleaner lifecycle, native browser EventSource |
| Env-only config | `.env` + `lyra.config.json` + per-agent files | Secrets in env, platform config in JSON, agent prompts/config on filesystem |
| MCP stub provider | Real stdio JSON-RPC MCP client | Enables immediate integration with MCP ecosystem (filesystem, shell servers) |
| Alembic migrations | Auto-created schemas | Sufficient for V1 single-dev use; Alembic warranted if schema evolution becomes complex |

### Features Added Beyond Roadmap

1. **Platform config system** (`lyra.config.json`): MCP servers, data dir, default model, embedding model, prompts dir — all configurable without code changes
2. **Agent file-based config**: `prompts/{agent-name}.md` for system prompts, `prompts/{agent-name}.json` for model/temperature/hitl_policy overrides. Falls back to `default.md`/`default.json`
3. **Real MCP stdio transport**: JSON-RPC over subprocess stdin/stdout with Windows .cmd resolution and Popen fallback for asyncio compatibility
4. **OpenRouter embedding provider**: Dual sync/async implementation — sync for ChromaDB's internal calls, async for protocol methods. Event emission from both paths
5. **Event inline summaries**: UI shows key payload info (tokens, tool names, queries) without expanding event details
6. **Smart auto-scroll**: Conversation and event panes only auto-scroll if user is already at the bottom

### V2 Readiness Assessment

The architecture is ready for V2 multi-agent work:
- `Agent.parent_agent_id` field exists (unused in V1)
- `AGENT_SPAWN` and `AGENT_COMPLETE` event types defined
- `ToolRegistry` pattern allows adding a `spawn_agent` tool
- Event bus supports agent_id filtering for per-agent streams
- Frontend agent detail page can be reused for child agents

**Recommended before starting V2:**
- Add explicit retry with backoff to OpenRouterProvider (currently try/except only)
- Consider cost tracking (OpenRouter provides cost data in usage)
- Evaluate whether agent persistence model needs revision (long-lived vs task-scoped)
- Add database migration tooling (Alembic) if V2 schemas grow complex