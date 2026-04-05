# Lyra Frontend Codebase Map

Technical reference for the Next.js/React/TypeScript frontend at `frontend/src/`.

## Overview

The frontend is a Next.js App Router application with 7 pages, real-time SSE event streaming, and a dark-themed terminal-style UI. All pages are client-side rendered (`"use client"`).

## Navigation

The root layout (`app/layout.tsx`) provides a global header with nav links: AGENTS, MEMORIES, KNOWLEDGE, EVENTS, GRAPH, CONFIG. The main content area fills the viewport height.

## API Client (`lib/api.ts`)

All backend communication goes through exported functions in `api.ts`. Base URL defaults to `http://localhost:8000`.

### Agent Management
- `fetchAgents()` → GET `/agents`
- `fetchAgent(id)` → GET `/agents/{id}`
- `createAgent(name, config?)` → POST `/agents`
- `deleteAgent(id)` → DELETE `/agents/{id}`
- `fetchAgentChildren(id)` → GET `/agents/{id}/children`
- `fetchAgentCost(id)` → GET `/agents/{id}/cost`

### Agent Communication
- `sendPrompt(agentId, message)` → POST `/agents/{agentId}/prompt`
- `sendAgentMessage(agentId, content, messageType)` → POST `/agents/{agentId}/messages`
- `fetchAgentMessages(id)` → GET `/agents/{id}/messages`
- `respondHITL(agentId, approved, message?)` → POST `/agents/{agentId}/hitl-respond`

### Conversations and Events
- `fetchAgentConversations(id)` → GET `/agents/{id}/conversations`
- `fetchAgentEvents(id, params?)` → GET `/agents/{id}/events`
- `fetchGlobalEvents(params?)` → GET `/events`

### Memory
- `fetchMemories(params?)` → GET `/memories` (supports agent_id, memory_type, q, archived, limit)
- `deleteMemory(id)` → DELETE `/memories/{id}`
- `updateMemory(id, patch)` → PATCH `/memories/{id}`

### Knowledge
- `fetchKnowledgeSources()` → GET `/knowledge/sources`
- `fetchKnowledgeChunks(source?)` → GET `/knowledge/chunks`
- `searchKnowledge(q, topK?)` → GET `/knowledge/search`

## Hooks

### useEventStream (`hooks/useEventStream.ts`)

Manages a Server-Sent Events connection for real-time event streaming.

**Parameters:** `agentId?: string` — If provided, connects to `/agents/{agentId}/events/stream`. Otherwise connects to the global `/events/stream`.

**Returns:** `{ events, connectionState, connect, disconnect }`

**Behavior:**
- Auto-connects on mount, auto-reconnects after 3 seconds on error
- Manual disconnect prevents auto-reconnect
- Events accumulate in state array
- Connection states: connecting, connected, disconnected

**Used by:** Home page (global), agent detail (per-agent), events page (global), memories page (global)

### useGraphData (`hooks/useGraphData.ts`)

Aggregates agent topology, inter-agent messages, and orchestration data for the graph visualization.

**Returns:** `{ agents, messages, orchestrations, connectionState, connect, disconnect, refresh }`

**Behavior:**
1. Fetches all agents on mount
2. For each agent, fetches orchestration events and parses subtask details (dependencies, statuses, synthesis)
3. Subscribes to global SSE stream
4. On relevant events (agent_spawn, agent_complete, llm_request, hitl_*, message_sent), debounced refresh of agents and orchestrations
5. Message_sent events are appended to the messages array for edge rendering

**Used by:** Graph page only

## Pages

### Home Page (`app/page.tsx`) — Route: `/`

Agent management dashboard. Lists all agents with status, model, and cost. Provides create and delete agent functionality.

**Data flow:**
1. On mount: `fetchAgents()` then `fetchAgentCost()` for each
2. SSE via `useEventStream()` for connection status display
3. Create agent form → `createAgent()` → refresh
4. Delete button → `deleteAgent()` → refresh

**Components used:** `AgentList`, `ConnectionStatus`

### Agent Detail Page (`app/agents/[id]/page.tsx`) — Route: `/agents/{id}`

Deep dive into a single agent with conversation, events, HITL controls, sub-agents, and inter-agent messaging.

**Layout:** Two-column grid. Left: conversation + prompt input + HITL panel + message panel. Right: event timeline.

**Data flow:**
1. On mount: parallel fetch of agent, events, conversations, cost, children, messages
2. SSE subscription to `/agents/{agentId}/events/stream`
3. Live events trigger targeted refreshes:
   - hitl_request/response/error/agent_complete → refresh agent status
   - message_sent/received → refresh messages and children
   - agent_spawn/complete → refresh children
   - agent_complete/llm_response → refresh conversation (skips mid-turn to prevent optimistic message from disappearing)

**Features:**
- Collapsible CONFIG panel showing model, temperature, max_iterations, hitl_policy, max_context_tokens, memory_top_k, allowed_tools, and full system prompt
- Sub-agents section with links and status badges
- Optimistic message rendering (human message appears immediately before API response)

**Components used:** `ConversationPanel`, `EventTimeline`, `ConnectionStatus`, `HITLPanel`, `MessagePanel`, `PromptInput`

### Memories Page (`app/memories/page.tsx`) — Route: `/memories`

Browse and manage agent memories with semantic search, type filtering, and archive controls.

**Data flow:**
1. On mount: `fetchMemories({ limit: 100 })`
2. Search/filter form → re-fetch with parameters
3. Delete → `deleteMemory()` → reload
4. Archive/unarchive → `updateMemory({ archived })` → reload

**Display:** Expandable memory list. Collapsed: type (color-coded), content preview, importance, decay, visibility. Expanded: full content, metadata (agent, dates, access count), action buttons.

### Knowledge Page (`app/knowledge/page.tsx`) — Route: `/knowledge`

Tree-structured knowledge base browser with semantic search.

**Data flow:**
1. On mount: `fetchKnowledgeSources()` for stats, `fetchKnowledgeChunks()` for browse mode
2. `buildTree()` organizes chunks into directory → source → chunks hierarchy
3. Common path prefix is stripped for cleaner display
4. Chunks without a directory are grouped under NO-PATH
5. Search mode: `searchKnowledge(query)` replaces chunks, results also shown in tree form

**Tree structure:**
- Directory nodes (yellow, collapsible, show chunk counts)
- Source/file nodes (green, collapsed by default, expand to show chunks)
- Chunk nodes (expandable, show heading path, content preview, char count)

### Events Page (`app/events/page.tsx`) — Route: `/events`

Global event stream monitor with filtering.

**Data flow:**
1. On mount: `fetchGlobalEvents({ limit: 200 })` + `fetchAgents()` for agent name resolution
2. SSE via `useEventStream()` merges live events (deduped by id)
3. Auto-scrolls to bottom on new events

**Filters:** Three dropdowns — event type, module, source agent. All work together. Agent IDs are resolved to names where possible.

**Display:** Expandable event rows with color-coded type, inline summary (model, tokens, cost, tool name, etc.), first 150 chars of payload JSON, agent link, module, timestamp. Expand for full payload JSON.

### Graph Page (`app/graph/page.tsx`) — Route: `/graph`

Real-time agent topology and orchestration visualization using ReactFlow.

**Data flow:**
1. `useGraphData()` loads agents, messages, orchestrations
2. `buildNodes()` creates agent nodes with optional subtask rows
3. `buildEdges()` creates parent-child edges + message edges (deduped, most recent per agent pair)
4. `layoutGraph()` uses dagre for hierarchical top-to-bottom layout
5. Filters control message types, time range, and subtask/message visibility
6. Click agent node → navigate to detail page

**Components used:** `GraphCanvas`, `AgentNode`, `ParentChildEdge`, `MessageEdge`, `DashboardHeader`, `GraphFilters`, `SpawnAgentForm`

### Config Page (`app/config/page.tsx`) — Route: `/config`

Platform configuration editor for all config surfaces.

**Data flow:**
1. On mount: `GET /config/files` → file tree organized by category (platform, agent_configs, agent_prompts, system_prompts, skills, mcp_servers)
2. Select file → `GET /config/file?path=X` → load content
3. Save → `PUT /config/file` with path + content
4. Delete → `DELETE /config/file?path=X`
5. Reload → `POST /config/reload` (hot reload)
6. Restart → `POST /config/restart` → poll `/health` until back online

**Features:** Context-sensitive help based on cursor position in config files. Shows descriptions for config keys like defaultModel, hitl policy, temperature, etc.

## Components

### Agent Display

**AgentList** (`AgentList.tsx`) — Grid of agent cards with name (linked), status badge (animated for running/waiting), model, cost, delete button. Status colors: green=running, orange=waiting_hitl, blue=completed, red=failed, gray=idle.

### Conversation and Events

**ConversationPanel** (`AgentDetail.tsx`) — Scrollable message list. Filters out tool_result and system messages, and empty tool-calling assistant turns. Color-codes by role. Detects inter-agent messages (prefixed with `[type from ...]`) and colors them orange.

**EventTimeline** (`AgentDetail.tsx`) — Expandable event list with color-coded types. Inline summaries extract key info from payloads (model, token counts, cost, tool names, success/fail, memory queries). Click to expand full JSON payload. Auto-scrolls to bottom.

**Event colors:** llm_request=#6688ff, llm_response=#4466dd, tool_call=#aa66ff, tool_result=#8844cc, memory_read=#00ff41, memory_write=#00cc33, hitl_request=#ffaa00, hitl_response=#cc8800, error=#ff3333, agent_spawn=#00ccff, agent_complete=#0099cc

### Interaction

**PromptInput** (`PromptInput.tsx`) — Text input + Send button. Clears on submit, auto-focuses after re-enable.

**HITLPanel** (`HITLPanel.tsx`) — Shows pending HITL requests with tool name, args preview, optional message input, and OK/NO buttons.

**MessagePanel** (`MessagePanel.tsx`) — Inter-agent message display with send form. Type selector dropdown (task, result, question, answer, guidance, status_update). Color-codes by type, shows direction arrows.

**ConnectionStatus** (`ConnectionStatus.tsx`) — SSE status badge: LIVE (green), CONNECTING (orange), OFFLINE (red). Clickable when handlers provided.

### Graph Visualization

**GraphCanvas** (`graph/GraphCanvas.tsx`) — ReactFlow wrapper with zoom controls, minimap, background grid. Custom node and edge types.

**AgentNode** (`graph/AgentNode.tsx`) — Agent card in graph showing name, status, model, and optional subtask list with status dots. Border color matches agent status.

**ParentChildEdge** (`graph/ParentChildEdge.tsx`) — Straight gray edge between parent and child. Dashed animation when child is running.

**MessageEdge** (`graph/MessageEdge.tsx`) — Curved bezier edge with message type label. Low opacity, high curvature to separate from parent-child edges.

**DashboardHeader** (`graph/DashboardHeader.tsx`) — Agent count + status breakdown with colored dots.

**GraphFilters** (`graph/GraphFilters.tsx`) — Toggle messages/subtasks visibility, filter by message type, select time range (1m to All).

**SpawnAgentForm** (`graph/SpawnAgentForm.tsx`) — Quick agent creation form with name + optional model.

**graphUtils.ts** — `buildNodes()`, `buildEdges()`, `layoutGraph()` (dagre hierarchical layout). Deduplicates message edges, computes dynamic node heights based on subtask count.

## Styling

- Dark theme with neon accents: green (#00ff41), orange (#ffaa00), cyan (#00ccff), purple (#aa66ff)
- Monospace font (JetBrains Mono / Fira Code)
- Terminal-style aesthetic with 1px borders, minimal padding
- Status animations: pulse-glow for running/waiting agents, blink for in-flight prompts
- Consistent color coding across all pages for status, event types, and message roles
