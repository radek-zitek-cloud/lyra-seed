# V3 Phase 4 — Plan

## Phase Reference
- **Version:** V3
- **Phase:** 4
- **Title:** Learning, Reflection & Capability Formalization
- **Roadmap Section:** V3P4

## Prerequisites
- [x] V3 Phase 2: Tool Creation — MCP Servers — COMPLETE

## Deliverables Checklist
- [ ] 4.1: `analyze_capabilities` tool — structured gap analysis across skills, templates, tools, MCP servers
- [ ] 4.2: `capability-acquirer` agent template — search-first approach to filling capability gaps
- [ ] 4.3: `reflect` tool — post-task retrospective stored as PROCEDURE memory
- [ ] 4.4: `tool_analytics` tool — query tool success rates and latency from event data
- [ ] 4.5: `store_pattern` and `find_pattern` tools — reusable orchestration patterns
- [ ] 4.6: Update system prompt with new tools and guidance

## Implementation Steps

### 1. analyze_capabilities tool
**Files:** `backend/src/agent_platform/tools/capability_tools.py`

- `analyze_capabilities(task)` tool
- Performs semantic search across all discovery sources:
  - `list_skills(query=task)` — matching skills
  - `list_templates(query=task)` — matching agent templates
  - `list_mcp_servers(query=task)` — matching MCP servers
  - `recall(query=task)` — relevant memories/knowledge
- Returns structured report:
  ```json
  {
    "task": "...",
    "available": {
      "skills": [...],
      "templates": [...],
      "mcp_servers": [...],
      "relevant_memories": [...]
    },
    "assessment": "LLM-generated gap analysis and acquisition plan"
  }
  ```
- The assessment is an LLM call that reviews what was found and identifies gaps
- Uses the orchestration model for the assessment call

### 2. capability-acquirer agent template
**Files:** `prompts/capability-acquirer.json`, `prompts/capability-acquirer.md`

- Config: no MCP tools (pure reasoning + platform tools), low temperature
- System prompt guides the workflow:
  1. Receive capability gap description from parent
  2. Search for existing skills (`list_skills`)
  3. Search for existing templates (`list_templates`)
  4. Search for existing MCP servers (`list_mcp_servers`)
  5. Search the web for MCP server packages (firecrawl)
  6. If found: `add_mcp_server` or recommend existing
  7. If not found: `create_skill` or `create_mcp_server`
  8. Report back to parent via `send_message`

### 3. reflect tool
**Files:** `backend/src/agent_platform/tools/capability_tools.py`

- `reflect(task, outcome, tools_used)` tool
- Generates a retrospective via LLM call:
  - What was the task?
  - What approach was taken?
  - What tools were used and how effective were they?
  - What was missing or could be improved?
  - What should be remembered for next time?
- Stores the reflection as a PROCEDURE memory via the memory store
- Uses the orchestration model
- Reflection prompt externalized to `prompts/system/reflect.md`

### 4. tool_analytics tool
**Files:** `backend/src/agent_platform/tools/capability_tools.py`

- `tool_analytics(tool_name?, top_n?)` tool
- Queries the event bus for TOOL_CALL and TOOL_RESULT events
- Aggregates: call count, success rate, avg duration, last used
- If `tool_name` provided: stats for that specific tool
- If omitted: top N tools by usage
- No new storage — reads from existing event data

### 5. store_pattern and find_pattern tools
**Files:** `backend/src/agent_platform/tools/capability_tools.py`

- Patterns stored as memories with memory_type=PROCEDURE
- `store_pattern(task_type, strategy, subtasks, notes)` — stores an orchestration pattern as a structured PROCEDURE memory
- `find_pattern(task_description)` — semantic search over PROCEDURE memories for matching patterns
- Both use the existing memory system (ChromaDB) — no new storage

### 6. Update system prompt
**Files:** `prompts/default.md`

- Document analyze_capabilities, reflect, tool_analytics, find_pattern, store_pattern
- Guidance: use analyze_capabilities before complex tasks, reflect after, store patterns for reuse

## File Manifest
**New:**
- `backend/src/agent_platform/tools/capability_tools.py` — all new tools
- `prompts/capability-acquirer.json` — template config
- `prompts/capability-acquirer.md` — template system prompt
- `prompts/system/reflect.md` — reflection prompt
- `backend/tests/smoke/test_v3_phase_4.py` — smoke tests

**Modified:**
- `backend/src/agent_platform/api/main.py` — wire CapabilityToolProvider
- `prompts/default.md` — document new tools

## Risks & Decisions
- analyze_capabilities makes multiple provider calls (skills, templates, MCP servers, memory) — may be slow. Accept this since it's called once at task start, not per iteration
- Patterns stored as PROCEDURE memories — reuses existing memory system rather than a new store. Simpler but means patterns compete with other memories in recall
- reflect uses LLM to generate the retrospective — could be expensive for minor tasks. Agent should only reflect on complex/orchestrated work
- tool_analytics reads raw events — with many events this could be slow. Limit to recent events (last 24h or configurable)
