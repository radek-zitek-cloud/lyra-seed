# Lyra Backend Codebase Map

Technical reference for the Python/FastAPI backend at `backend/src/agent_platform/`.

## Module Overview

The backend has 9 modules: `api`, `core`, `db`, `llm`, `memory`, `knowledge`, `observation`, `orchestration`, `tools`. All modules are async-first and emit events via the EventBus for observability.

## API Module

The `api/` module contains the FastAPI app factory, route handlers, and dependency injection.

### App Factory (`main.py`)

`create_app(settings)` wires up the entire application:
- Creates all repositories (agent, conversation, message)
- Initializes LLM provider (OpenRouter) and embedding provider
- Creates memory system (ChromaMemoryStore, ContextManager, FactExtractor)
- Sets up tool registry and registers all providers (skills, templates, MCP, memory, knowledge, orchestration, spawner, discovery, capabilities)
- Ingests knowledge base on startup from `knowledgeDir`
- Connects MCP servers on startup
- Registers all route modules

### Routes

- `routes.py` — Agent CRUD, prompt submission, HITL response
- `observation_routes.py` — Events (per-agent and global), conversations, tools, cost
- `memory_routes.py` — Memory CRUD with semantic search
- `knowledge_routes.py` — Knowledge sources, chunks, semantic search
- `skill_routes.py` — Skill listing
- `template_routes.py` — Template listing
- `config_routes.py` — Platform config file editor, reload, restart
- `message_routes.py` — Inter-agent messaging
- `ws_routes.py` — SSE event streams (per-agent and global)

### Dependency Injection (`_deps.py`)

Module-level singletons set during startup via `configure()`. Getters like `get_agent_repo()`, `get_runtime()`, `get_knowledge_store()` are used by route handlers to access shared instances.

## Core Module

The `core/` module contains the agent runtime loop, data models, and configuration.

### Models (`models.py`)

- `AgentStatus` — Enum: IDLE, RUNNING, WAITING_HITL, COMPLETED, FAILED
- `HITLPolicy` — Enum: ALWAYS_ASK, DANGEROUS_ONLY, NEVER
- `AgentConfig` — Full agent configuration: model, temperature, max_iterations, system_prompt, allowed_tools, hitl_policy, hitl_timeout_seconds, retry settings, memory settings (prune_threshold, prune_max_entries, max_context_tokens, memory_top_k), summary_model, extraction_model, memory_sharing, allowed_mcp_servers
- `Agent` — Core entity: id, name, status, config, parent_agent_id, timestamps
- `Conversation` — Agent conversation with message list
- `AgentResponse` — Result of agent.run(): agent_id, content, conversation_id, events_emitted
- `MessageType` — Inter-agent message types: TASK, RESULT, QUESTION, ANSWER, GUIDANCE, STATUS_UPDATE
- `AgentMessage` — Message between agents: from/to agent_id, content, type, timestamp, in_reply_to

### Agent Runtime (`runtime.py`)

`AgentRuntime.run(agent_id, human_message)` executes the core agent loop:

1. Fetches agent from DB, sets status to RUNNING
2. Gets or creates conversation, injects system prompt
3. Calls `ContextManager.assemble()` to inject relevant memories
4. Loops until max_iterations or no tool calls:
   - Injects pending GUIDANCE messages from other agents
   - Calls LLM via `OpenRouterProvider.complete()` with tool schemas
   - If no tool calls: stores response, runs `FactExtractor.extract()`, prunes stale memories, returns
   - If tool calls: checks HITL gate, executes each tool via `ToolRegistry.call_tool()`, appends results, continues loop
5. Returns `AgentResponse`

Other methods:
- `hitl_respond(agent_id, approved, message)` — Resumes agent after HITL approval/denial
- `cleanup_stuck_agents()` — Resets stuck RUNNING/WAITING_HITL agents on startup

### Platform Config (`platform_config.py`)

`load_platform_config(project_root)` loads `lyra.config.json`. `AgentFileConfig` loads per-agent config from `prompts/{name}.json`. Resolution chain: agent-specific config → platform defaults → hardcoded defaults.

## DB Module

The `db/` module provides async SQLite repositories behind abstract protocols.

- `Repository` — Abstract CRUD protocol: get, list, create, update, delete
- `SqliteAgentRepo` — Agent persistence with WAL mode
- `SqliteConversationRepo` — Conversation persistence with agent_id filtering
- `SqliteMessageRepo` — Inter-agent message persistence
- `VectorStore` — Abstract protocol for vector storage (store, search, delete)

All repositories use aiosqlite for async operations and are initialized with `initialize()` which creates tables.

## LLM Module

The `llm/` module abstracts LLM providers behind a protocol interface.

### Models (`models.py`)

- `MessageRole` — HUMAN, ASSISTANT, SYSTEM, TOOL_RESULT
- `Message` — Conversation message with optional tool_calls and tool_call_id
- `ToolCall` — LLM tool invocation: id, name, arguments dict
- `LLMResponse` — LLM output: content, tool_calls, usage dict, raw_response
- `LLMConfig` — Call parameters: model, temperature, max_tokens

### OpenRouter Provider (`openrouter.py`)

`OpenRouterProvider.complete(messages, tools, config, agent_id)`:
- Sends requests to `https://openrouter.ai/api/v1/chat/completions`
- Converts tools to OpenAI function-calling schema
- Emits LLM_REQUEST and LLM_RESPONSE events with cost tracking
- Supports configurable retry with exponential backoff
- Computes USD cost from token usage and model pricing

### Embeddings (`openrouter_embeddings.py`)

`OpenRouterEmbeddingProvider` provides embeddings via `https://openrouter.ai/api/v1/embeddings`. Default model: `openai/text-embedding-3-large`. Dual-client design: async for protocol compliance, sync adapter for ChromaDB's synchronous API.

## Memory Module

The `memory/` module implements three-layer semantic memory with automatic lifecycle management.

### Memory Store (`chroma_memory_store.py`)

`ChromaMemoryStore` uses ChromaDB for vector-backed memory storage:
- `add(entry)` — Stores memory with deduplication check (cosine similarity threshold)
- `search(query, agent_id, memory_type, top_k, include_public, exclude_archived)` — Semantic search with visibility and type filtering
- `list_by_agent(agent_id)` — List all memories for an agent
- `update(id, patch)` / `delete(id)` — CRUD operations
- Supports cross-agent memory via visibility levels: PRIVATE, TEAM, PUBLIC, INHERIT

### Memory Types

`MemoryType` enum: EPISODIC, PREFERENCE, DECISION, OUTCOME, FACT, PROCEDURE, TOOL_KNOWLEDGE, DOMAIN_KNOWLEDGE. Each memory has importance (0-1), decay_score, access_count, and timestamps.

### Context Manager (`context_manager.py`)

`ContextManager.assemble(agent_id, messages, query, top_k, max_context_tokens)`:
- Retrieves top-k relevant memories via semantic search
- Injects memories as SYSTEM messages into conversation
- Compresses messages to fit token budget by summarizing old messages via LLM
- Updates access_count on retrieved memories

### Fact Extractor (`extractor.py`)

`FactExtractor.extract(agent_id, assistant_message, conversation_context)`:
- Calls LLM to extract facts, preferences, decisions from the agent's response
- Creates MemoryEntry objects with appropriate types and visibility
- Stores via ChromaMemoryStore, never breaks the agent loop on failure

### Memory Decay (`decay.py`)

`TimeDecayStrategy` calculates decay scores based on age, access frequency, and importance. `ChromaMemoryStore.prune()` removes entries below threshold after each agent run.

### Memory Tools (`memory_tools.py`)

`MemoryToolProvider` exposes `remember`, `recall`, `forget` as tools agents can call directly during their execution loop.

## Knowledge Module

The `knowledge/` module provides RAG-based document retrieval from markdown files.

### Chunker (`chunker.py`)

`chunk_markdown(path)` splits markdown files into `DocumentChunk` objects at heading boundaries. Each chunk has: content, source (filename), heading_path (hierarchical path like "Memory System > Context Memory"), directory.

### Knowledge Store (`store.py`)

`KnowledgeStore` uses ChromaDB with cosine similarity:
- `ingest(path)` — Chunks, embeds, stores a markdown file. Re-ingesting replaces old chunks from same source.
- `ingest_directory(dir_path)` — Batch ingest all .md files (skips README)
- `search(query, top_k)` — Semantic search returning DocumentChunk objects
- `get_sources()` — List ingested document names
- `get_chunks(source)` — Retrieve chunks by source

### Knowledge Tools (`tools.py`)

`KnowledgeToolProvider` exposes `search_knowledge` and `ingest_document` as agent tools.

## Observation Module

The `observation/` module provides event-driven observability and cost tracking.

### Event Types (`events.py`)

`EventType` enum: LLM_REQUEST, LLM_RESPONSE, TOOL_CALL, TOOL_RESULT, MEMORY_READ, MEMORY_WRITE, AGENT_SPAWN, AGENT_COMPLETE, HITL_REQUEST, HITL_RESPONSE, MESSAGE_SENT, MESSAGE_RECEIVED, ERROR.

`Event` model: id (UUID), timestamp, agent_id, event_type, parent_event_id, module, payload dict, duration_ms.

`EventFilter` for querying: agent_id, event_types, time_from/to, module, parent_event_id.

### Event Bus (`in_process_event_bus.py`)

`InProcessEventBus`:
- `emit(event)` — Broadcasts to matching subscribers and persists to SQLite
- `subscribe(event_types, agent_id)` — Returns async iterator of filtered events
- `query(filters)` — Queries persisted events from SQLite
- Used by SSE endpoints for real-time streaming

### Event Store (`sqlite_event_store.py`)

`SqliteEventStore` persists events to SQLite for historical querying.

### Cost Tracker (`cost_tracker.py`)

`compute_agent_cost(event_bus, agent_id)` and `compute_total_cost(event_bus)` aggregate LLM costs from LLM_RESPONSE events.

## Orchestration Module

The `orchestration/` module handles task decomposition and multi-strategy execution.

### Models (`models.py`)

- `SubTask` — Task unit: id, description, assigned_to, dependencies, status, result, failure_policy, retry tracking
- `TaskPlan` — Decomposed plan: subtasks list, strategy type, status
- `OrchestrationResult` — Execution result: plan_id, results, synthesized_response, status
- `OrchestrationStrategyType` — SEQUENTIAL, PARALLEL, PIPELINE
- `FailurePolicy` — RETRY, REASSIGN, ESCALATE, SKIP

### Task Decomposer (`decomposer.py`)

`TaskDecomposer.decompose(task, tools, llm, max_subtasks)` calls LLM to break a complex task into subtasks with dependencies and strategy selection.

### Execution Strategies (`strategies.py`)

- `SequentialOrchestration` — Executes subtasks in order, passing results forward
- `ParallelOrchestration` — Runs independent subtasks concurrently
- `PipelineOrchestration` — Chains subtasks where each output feeds the next input

Subtask execution dispatches to: spawn_agent (for sub-agents), registered tools (via ToolRegistry), or direct LLM calls as fallback.

### Result Synthesizer (`synthesizer.py`)

`ResultSynthesizer.synthesize(task, results)` calls LLM to merge subtask results into a coherent final response.

### Orchestration Tools (`tool_provider.py`)

`OrchestrationToolProvider` exposes `decompose_task` and `orchestrate` tools. The `orchestrate` tool runs the full pipeline: decompose → execute → synthesize.

## Tools Module

The `tools/` module aggregates all tool providers behind a unified registry.

### Core (`registry.py`, `models.py`)

- `Tool` — Definition: name, description, input_schema (JSON Schema), tool_type (MCP|INTERNAL), source
- `ToolResult` — Execution result: success, output, error, duration_ms
- `ToolProvider` — Abstract protocol: list_tools(), call_tool(name, arguments)
- `ToolRegistry` — Central registry that aggregates providers, filters by allowed_tools/allowed_mcp_servers, routes calls to correct provider, converts to OpenAI function schema

### Skill Provider (`skill_provider.py`)

Loads prompt templates from `skills/*.md` (with YAML frontmatter). Tools: `list_skills`, `create_skill`, `test_skill`, `update_skill`, `delete_skill`. Supports semantic search via embeddings and LLM-based skill evaluation.

### Template Provider (`template_provider.py`)

Scans `prompts/` directory for paired `.json` + `.md` agent templates. Tools: `list_templates`, `get_template`. Supports semantic search.

### MCP Client (`mcp_client.py`)

`MCPStdioClient` implements JSON-RPC stdio transport for Model Context Protocol servers. `MCPClientProvider` manages multiple MCP server connections, routing tool calls to the appropriate server.

### MCP Server Manager (`mcp_server_manager.py`)

`MCPServerManager` manages agent-created MCP servers. Discovers `.py` server scripts, handles spawning and deployment. Tools: `list_mcp_servers`, `deploy_mcp_server`.

### Agent Spawner (`agent_spawner.py`)

`AgentSpawnerProvider` manages sub-agent lifecycle:
- `spawn_agent` — Creates child agent with async execution, enforces max_spawn_depth
- `wait_for_agent` — Blocks until child completes
- `check_agent_status` — Non-blocking status check
- `get_agent_result` — Retrieves final response
- `list_child_agents` — Lists children of current agent
- `stop_agent` — Cancels running agent

### Agent Messaging (`agent_messaging.py`, `agent_lifecycle.py`)

Inter-agent communication tools: `send_message`, `receive_messages`. Messages are typed (task, result, question, answer, guidance, status_update) and stored via `SqliteMessageRepo`.

### Discovery Provider (`discovery_provider.py`)

`DiscoveryProvider` exposes a unified `discover(query)` tool that searches across all capability dimensions: skills, agent templates, MCP server tools, knowledge chunks, and memories. Returns ranked results.

### Capability Tools (`capability_tools.py`)

`CapabilityToolProvider` exposes self-improvement tools:
- `analyze_capabilities` — Gap analysis of available tools vs needs
- `reflect` — Post-task retrospective via LLM
- `tool_analytics` — Usage statistics from event history
- `store_pattern` — Save orchestration patterns for reuse

## Key Data Flows

### Prompt to Response

```
POST /agents/{id}/prompt
  → AgentRuntime.run(agent_id, message)
    → ContextManager.assemble() → injects memories as SYSTEM messages
    → Loop:
      → Inject pending GUIDANCE messages
      → OpenRouterProvider.complete() → LLM call with tools
      → If tool calls: HITL check → ToolRegistry.call_tool() → append results
      → If no tool calls: store response → FactExtractor.extract() → prune memories → return
```

### Memory Lifecycle

```
After each agent response:
  FactExtractor → LLM extracts facts → ChromaMemoryStore.add() (with dedup)

Before each LLM call:
  ContextManager → ChromaMemoryStore.search() → inject as SYSTEM messages

After each successful run:
  TimeDecayStrategy → prune stale memories
```

### Orchestration

```
orchestrate(task)
  → TaskDecomposer.decompose() → LLM breaks into subtasks
  → Execute via strategy (Sequential/Parallel/Pipeline):
    → spawn_agent / ToolRegistry.call_tool() / direct LLM
  → ResultSynthesizer.synthesize() → LLM merges results
```

### Event Flow

```
Any action → InProcessEventBus.emit(event)
  → SqliteEventStore.persist()
  → Broadcast to SSE subscribers
  → Frontend receives via EventSource
```
