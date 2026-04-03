# V2 Phase 5: Observation UI — Multi-Agent & Orchestration Graph

## Overview

Add a new `/graph` page with an interactive React Flow visualization showing agent hierarchy, orchestration subtasks, and inter-agent messages in real-time. This is a **separate view** alongside the existing observation UI — no existing pages are modified.

Incorporates BL-006 (Basic + Enhanced tiers). BL-007 (timeline scrubber) deferred.

## Prerequisites

- V2 Phase 4 complete (or all prior phases passing)
- No backend changes needed

## Deliverables

- [x] 5.1 Agent network graph (React Flow, parent-child edges, status colors, click-to-drill)
- [x] 5.2 Orchestration subtask visualization (subtask pills inside agent nodes, status coloring)
- [x] 5.3 Communication flow (message edges with type labels, filterable)
- [x] 5.4 Dashboard & spawning (stats bar, root agent creation form)

## Dependencies

- `@xyflow/react` ^12 — React Flow graph library
- `@dagrejs/dagre` ^1 — Hierarchical auto-layout

## File Manifest

### New
- `frontend/src/app/graph/page.tsx` — Graph page route
- `frontend/src/components/graph/GraphCanvas.tsx` — React Flow canvas
- `frontend/src/components/graph/AgentNode.tsx` — Custom agent node
- `frontend/src/components/graph/MessageEdge.tsx` — Custom message edge
- `frontend/src/components/graph/ParentChildEdge.tsx` — Custom hierarchy edge
- `frontend/src/components/graph/DashboardHeader.tsx` — Stats bar
- `frontend/src/components/graph/GraphFilters.tsx` — Filter controls
- `frontend/src/components/graph/SpawnAgentForm.tsx` — Agent creation form
- `frontend/src/components/graph/graphUtils.ts` — Node/edge builder functions
- `frontend/src/hooks/useGraphData.ts` — Data fetching hook with SSE

### Modified
- `frontend/src/app/layout.tsx` — GRAPH nav link
- `frontend/package.json` — New dependencies

## Architecture

- Data from existing APIs: `/agents`, `/agents/{id}/events`, `/events/stream`
- Real-time via global SSE stream (no agentId)
- Dagre auto-layout for hierarchical positioning
- Agents as compound React Flow nodes, subtasks as DOM elements inside nodes
