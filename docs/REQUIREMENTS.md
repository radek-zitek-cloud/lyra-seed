# Requirements — Self-Evolving Multi-Agent Platform

> **Type:** Experimental hobby project
> **Author:** Radek Zítek / zitek.cloud
> **Model:** Single-human dedicated assistant

---

## 1. Agent Runtime

- Agent core loop: human prompt → context assembly → LLM request → response parsing → tool call loop and/or sub-agent spawn → final response
- Configurable agent behavior (model, temperature, system prompt, allowed tools, iteration limits)
- Agent lifecycle management (idle, running, waiting for human input, completed, failed)

## 2. Tool System

- Tools are the agent's interface to external capabilities
- Two tool types:
  - **Prompt macros / skills** — parameterized prompt templates that expand and execute as LLM sub-calls
  - **MCP server tools** — tools exposed by Model Context Protocol servers (stdio or HTTP/SSE transport)
- Unified tool interface: both tool types conform to the same contract (name, description, input schema, execute)
- Tool registry aggregating tools from all providers
- Per-agent tool scoping: each agent can have its own MCP server set configured via `{name}.json`, reducing token overhead and enforcing least-privilege access
- Self-evolution: agents can create new tools at runtime
  - Define and register new prompt macros
  - Scaffold, deploy, and register new MCP servers

## 3. Multi-Agent Orchestration

- Agents can spawn sub-agents with specific mandates and tool access
- Parent-child agent hierarchy with lifecycle tracking
- Task decomposition: complex tasks broken into subtasks mapped to tools or sub-agents
- Orchestration patterns: sequential, parallel, pipeline
- Result synthesis: parent collects and synthesizes sub-agent outputs via LLM

## 4. Inter-Agent Communication

- All agents can communicate with each other
- Message passing protocol with typed messages (task, result, question, answer, status update)
- Communication patterns: direct messaging, parent broadcast, result aggregation
- All messages persisted and observable

## 5. Layered Memory

- **Context memory** — working memory within a single agent run (conversation history, tool results, scratch state) with token budget management and compression strategies
- **Cross-context semantic memory** — autobiographical memory across sessions (session summaries, decisions made, user preferences observed, task outcomes) with vector-based semantic retrieval
- **Long-term semantic memory** — durable knowledge base (learned facts, domain knowledge, procedures, tool documentation) with vector-based semantic retrieval
- Memory exposed as agent tools (remember, recall, forget) so the agent decides when to use memory as part of its reasoning
- Abstract memory strategy pattern (initial implementation: time-decay with configurable half-life)

## 6. Observability

- Observability is foundational, not retrofitted — built from Phase 1
- Events replace logs: every significant action emits a structured event
- Events capture: LLM requests/responses, tool calls/results, memory reads/writes, agent spawning/completion, inter-agent messages, HITL interactions, errors
- Events are nested (parent-child) and grouped by module (e.g., "memory", "tools.mcp", "llm.openrouter")
- Events include timing data (duration), agent identity, and full payload
- Real-time event streaming via WebSocket for live observation

## 7. Human in the Loop (HITL)

- Human prompts the agent and receives responses
- Notification system for agent status changes and completed tasks
- Permission gates: configurable approval policies for tool calls (always ask, dangerous only, never)
- Agent execution pauses at permission gates until human approves or denies
- Human can annotate interactions ("remember this", correct agent behavior)

## 8. Observation UI

The web-based dashboard serves as the primary interface for monitoring and interacting with the system.

**Agent management:**
- Spawn new agents from the UI with configuration
- View agent list with status indicators
- Drill into individual agent detail (config, conversation, events)

**Network visualization:**
- Agent topology graph showing parent-child relationships
- Communication network between agents
- Message flow visualization with message content inspection

**Execution inspection:**
- Timeline of events within an agent (chronological, filterable by type and module)
- Nested event display (grouped operations shown with hierarchy)
- Tool call inspector: input arguments, output, duration, success/failure

**HITL interface:**
- Pending approval queue across all agents
- Approve/deny actions with optional human message
- HITL interaction history

## 9. Model Case

The end-to-end scenario the platform is designed to support:

1. Human prompts with a complex task
2. Main agent decomposes the task into subtasks
3. Agent maps subtasks to known skills, tools, and identifies capability gaps
4. Agent spawns acquisition sub-agent(s) to build or find missing capabilities
5. Agent spawns execution sub-agent(s) for known subtasks
6. Acquisition agents create new tools and register them
7. Main agent re-plans with newly available tools
8. Execution sub-agents complete their work
9. Main agent synthesizes a unified response

## 10. Architecture Principles

- **Abstraction-first:** Every major subsystem fronted by an abstract interface with a simple initial implementation, enabling future swap-out without rewrites
- **Single-user model:** The system serves one human; no multi-tenancy in scope
- **Cross-platform:** All tooling and runtime must work on both Linux and Windows
- **Smoke-test-driven development:** Every phase defines automated smoke tests before implementation; phase completion gated by test results

---

## Post-V1 Addendum

This section documents what was delivered, what deviated from the original requirements, and what remains incomplete after V1 implementation.

### Delivered (all V1 requirements met)

- **Agent Runtime (Req 1):** Full core loop implemented. Agent receives prompts, assembles context with memory injection, calls LLM, handles tool calls in a loop, returns responses. Configurable behavior (model, temperature, max_iterations, system_prompt, allowed_tools, hitl_policy). Lifecycle management with status transitions (IDLE, RUNNING, WAITING_HITL, COMPLETED, FAILED).
- **Tool System (Req 2):** Both tool types implemented. Prompt macros with `{{parameter}}` template expansion and LLM sub-calls. MCP server tools via real stdio JSON-RPC transport (not just stub). Unified ToolProvider protocol, ToolRegistry for aggregation and routing. Agents cannot yet create tools at runtime (V3 scope).
- **Layered Memory (Req 5):** Three tiers implemented. Context memory via ContextManager (memory injection before LLM calls). Cross-context semantic memory (EPISODIC, PREFERENCE, DECISION, OUTCOME types). Long-term semantic memory (FACT, PROCEDURE, TOOL_KNOWLEDGE, DOMAIN_KNOWLEDGE types). Memory exposed as tools (remember, recall, forget). TimeDecayStrategy with configurable half-life. ChromaDB for vector storage (deviation from sqlite-vec — see below).
- **Observability (Req 6):** Event system is foundational, built from Phase 1. All 13 event types implemented. Events are nested (parent_event_id), grouped by module, include timing data. Real-time streaming via SSE (deviation from WebSocket — see below).
- **HITL (Req 7):** Permission gates with configurable policies (ALWAYS_ASK, DANGEROUS_ONLY, NEVER). Agent execution pauses at gates until human responds. Approval/denial via API endpoint and frontend panel.
- **Observation UI (Req 8):** Full web dashboard. Agent management (create, view, delete). Event timeline with expandable details and inline summaries. Tool call inspector with input/output display. HITL approval panel. Real-time updates via SSE. Connection status indicator.

### Deviations from original requirements

| Aspect | Original | Implemented | Rationale |
|--------|----------|-------------|-----------|
| Vector storage | sqlite-vec | ChromaDB | More mature, better metadata filtering, handles embeddings natively |
| Real-time streaming | WebSocket | SSE (Server-Sent Events) | Simpler lifecycle, no shutdown issues, native browser EventSource |
| Configuration | Env vars only | Env vars + `lyra.config.json` + per-agent file-based config | Better separation of secrets (env) vs platform config (JSON) vs agent config (prompts dir) |
| MCP client | "MCP client" (implied stub) | Full stdio JSON-RPC transport with Windows support | Enables immediate real-world MCP server integration |
| Embedding provider | "Behind abstract interface" | Dual sync/async implementation for ChromaDB compatibility | ChromaDB calls embeddings synchronously; needed both interfaces |

### Post-V2P1 & V2P2 Addendum

- **Multi-Agent Orchestration (Req 3):** Sub-agent spawning delivered in V2P1. Async spawning, lifecycle management (check_agent_status, stop_agent, wait_for_agent, dismiss_agent) delivered in V2P2. Sub-agents run with full tool access and their own iteration budgets.
- **Inter-Agent Communication (Req 4):** Full message bus delivered in V2P2. Six message types (TASK, RESULT, QUESTION, ANSWER, GUIDANCE, STATUS_UPDATE). Message persistence in SQLite. MESSAGE_SENT/MESSAGE_RECEIVED events. Auto-wake: idle agents automatically start a runtime turn when receiving TASK or GUIDANCE messages. Consumed messages are deleted after processing.
- **Reusable Agent Lifecycle:** Sub-agents persist after task completion (IDLE state). Parents can send new tasks via messages. Workers auto-report results back to the requesting agent. Parent-child navigation in UI (SUB-AGENTS bar + PARENT link).
- **Message Bus Observability:** MessagePanel in agent detail UI showing messages with type badges, direction indicators, timestamps. Send message input with type selector. Auto-refresh on SSE message events.
- **Memory Browser:** Dedicated /memories page with semantic search, type/status filtering, archive/unarchive/delete operations.
- **Configuration:** Agent config from `{name}.json` files (model, hitl_policy, temperature, max_iterations, auto_extract). Platform config from `lyra.config.json` (dataDir, defaultModel, embeddingModel, mcpServers, retry, memoryGC, context). Config reloads from disk on each agent creation.
- **Memory Deduplication:** Pre-write similarity check prevents duplicate memories (configurable threshold).

### Post-V2P3 Addendum

- **Orchestration Patterns (Req 3):** Task decomposition via LLM-based `TaskDecomposer` producing structured `TaskPlan` with subtasks, dependencies, and failure policies. Three orchestration strategies: `SequentialOrchestration` (ordered), `ParallelOrchestration` (concurrent via asyncio.gather), `PipelineOrchestration` (chained output-to-input). `ResultSynthesizer` combines subtask results into unified response via LLM. Four failure policies per subtask: retry, reassign, escalate, skip.
- **Orchestration Tools:** `decompose_task` (plan-only) and `orchestrate` (end-to-end: decompose + execute + synthesize) registered as agent tools. Agents use them autonomously based on system prompt guidance.
- **Orchestration Configuration:** `orchestrationModel` in `lyra.config.json` routes orchestration LLM calls to a cheaper model (e.g., gpt-5.4-mini) while the agent's main reasoning uses the full model. `maxSubtasks` caps decomposition to prevent runaway cost (default 10). Both configurable per-agent via `prompts/{name}.json`.
- **Externalized Prompts:** Decomposition and synthesis system prompts stored in `prompts/system/decompose_task.md` and `prompts/system/synthesize_results.md`, editable without code changes.

**Deviation from roadmap:** Subtasks execute as direct LLM calls, not as tool calls or sub-agent spawns. The `assigned_to` field exists on `SubTask` but is not used for routing — all subtasks get the same LLM-call execution. This was sufficient for analysis/writing tasks but means orchestrated subtasks cannot use tools, access memory, or run multi-iteration loops. See backlog BL-005 for the enhancement to wire `assigned_to` to actual tool/agent execution.

### Post-V2P4 Addendum

- **Per-Agent Tool Scoping (Req 2, 3):** `allowed_mcp_servers` field on `AgentConfig` controls which MCP servers' tools an agent sees (null = all, [] = none, ["filesystem"] = only filesystem). `allowed_tools` field provides explicit tool name whitelisting. Both filters apply at schema level — the LLM only sees allowed tools. Core tools (memory, spawner, orchestration) are never filtered by MCP scoping. Child agents inherit parent's tool scope; template overrides parent.
- **Agent Templates:** Pre-defined agent roles with per-agent tool scoping: `researcher` (no MCP tools), `writer` (no MCP), `editor` (no MCP), `critic` (no MCP), `coder` (filesystem + shell), `hitl-worker` (all tools, HITL enabled), `non-hitl-worker` (all tools, autonomous).
- **Configuration Guide:** Comprehensive `docs/CONFIGURATION_GUIDE.md` covering all config surfaces (.env, lyra.config.json, agent JSON, agent prompts, system prompts, skills), the four-level resolution chain, and examples for common agent roles.

### Post-V2P7 Addendum

- **Skills System (Req 2):** Replaced database-backed prompt macros with filesystem-based skills. Skills are `.md` files in `skills/` with YAML frontmatter (name, description, parameters) and a template body with `{{param}}` placeholders. `SkillProvider` scans the directory at startup and registers each skill as a tool. Skills execute via LLM sub-call using the calling agent's model. `create_skill` tool allows agents to create new skills at runtime by writing `.md` files. Removed `SqliteMacroRepo`, `macro_routes.py`, and database table.
- **Starter Skills:** Three bundled skills: `summarize` (bullet-point summaries), `translate` (language translation), `code-review` (code quality review).
- **Skills API:** Read-only `GET /skills` and `GET /skills/{name}` endpoints.
- **Simplified agent_id Injection:** Runtime now injects `agent_id` into all tool calls (not a hardcoded whitelist), supporting dynamic skill names.
- **Config Editor UI:** Web-based configuration editor at `/config` with sidebar file browser (Platform Config, Agent Configs, Agent Prompts, System Prompts, Skills), inline text editor with save/cancel, delete with inline confirmation (protected for platform config and system prompts), and cursor-aware context help bar showing descriptions for config keys.

### Post-V3 Addendum

- **Skill Lifecycle (V3P1):** `test_skill` dry-runs with two-call LLM evaluation (execute + assess PASS/FAIL). `update_skill` versions old files as `{name}.v{n}.md`. Name validation rejects invalid characters and reserved tool names. Semantic skill search via `list_skills(query="...")`. Deduplication rejects semantically similar descriptions (threshold 0.85).
- **MCP Server Management (V3P2):** `add_mcp_server` adds pre-built servers (npm/pip). `create_mcp_server` scaffolds custom server directories. `deploy_mcp_server` HITL-gated (human-only API, LLM cannot bypass). `list_mcp_servers` with semantic search. `stop_mcp_server` for agent-managed servers. Configs in `mcp-servers/*.json`. Hot-reload via `/config/reload`. Demonstrated end-to-end: agent built microblog MCP server from API docs.
- **Capability Analysis (V3P4):** `analyze_capabilities` searches skills, templates, MCP servers, and memories for a task, returns structured gap assessment. `reflect` generates post-task retrospective stored as PROCEDURE memory. `tool_analytics` aggregates success rates and latency from event data. `store_pattern` and `find_pattern` for reusable orchestration patterns. `capability-acquirer` agent template with search-first workflow.
- **Template Discovery:** `list_templates(query="...")` and `get_template` tools for semantic search over agent templates.
- **Multi-Agent Graph UI (V2P5):** React Flow graph visualization of agent hierarchy, orchestration subtasks, and message flows.
- **Mixed Subtask Execution (V2P6):** Orchestration subtasks can route to tools or sub-agents via `assigned_to` field.

### Post-V4P1 Addendum

- **Technical Cleanup (V4P1):** `LLMConfig` default model changed from `minimax/minimax-m2.7` to `None` (resolves from platform config). `ToolType.PROMPT_MACRO` renamed to `ToolType.INTERNAL`. Shared utilities extracted (`cosine_similarity`, `resolve_env_vars`). `capability_tools` resolves model from agent config.

### Not yet delivered

- **RAG Knowledge Base:** Document ingestion, chunking, and semantic search over `.md` knowledge base files
- **Unified Discovery (BL-008):** Single `discover(query)` tool searching across all capability sources
- **Content Pipeline:** End-to-end technical content pipeline (coordinator → researcher → writer → editor → critic)
- **Production Hardening:** Cost caps, error recovery, session persistence