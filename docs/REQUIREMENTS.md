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