# V4 Phase 3 — Plan

## Phase Reference
- **Version:** V4
- **Phase:** 3
- **Title:** Unified Capability Discovery (BL-008)
- **Roadmap Section:** POST_V3_ROADMAP.md V4P3

## Prerequisites
- [x] V4 Phase 2: RAG Knowledge Base — COMPLETE

## Deliverables Checklist
- [ ] 3.1: `discover(query)` tool — single search across skills, templates, MCP servers, knowledge, and memories
- [ ] 3.2: Unified result format — type, name, description, relevance score
- [ ] 3.3: Result ranking — merge results from all sources by relevance
- [ ] 3.4: Configurable source inclusion — agent can filter which sources to search
- [ ] 3.5: Update system prompt — document discover tool
- [ ] 3.6: Update analyze_capabilities to use discover internally

## Implementation Steps

### 1. Create DiscoveryProvider
**Files:** `backend/src/agent_platform/tools/discovery_provider.py`

- `discover(query, sources?, top_k?)` tool
- Searches across all capability sources in parallel:
  - Skills (via SkillProvider._list_skills)
  - Templates (via TemplateProvider._list_templates)
  - MCP servers (via MCPServerManager._list_servers)
  - Knowledge base (via KnowledgeStore.search)
  - Memories (via ChromaMemoryStore.search)
- Each source returns results with a relevance score
- Results merged and ranked by score across sources
- Returns unified format: `[{type, name, description, source, score}]`

### 2. Unified result format
Each result has:
- `type`: "skill" | "template" | "mcp_server" | "knowledge" | "memory"
- `name`: identifier (skill name, template name, document name, etc.)
- `description`: brief description or content preview
- `source`: where it came from (file name, collection, etc.)
- `score`: relevance score (0-1, from embedding similarity)

### 3. Source filtering
- `sources` parameter: optional list of source types to search
- Default: all sources
- Example: `discover(query="...", sources=["skills", "knowledge"])`

### 4. Wire into main.py
- DiscoveryProvider receives references to all other providers + stores
- Registered with ToolRegistry

### 5. Simplify analyze_capabilities
- Replace individual provider searches with a single `discover()` call
- analyze_capabilities becomes: discover + LLM assessment

### 6. System prompt
- Document `discover` tool
- Guidance: use discover as first step for any unfamiliar task

## File Manifest
**New:**
- `backend/src/agent_platform/tools/discovery_provider.py`
- `backend/tests/smoke/test_v4_phase_3.py`

**Modified:**
- `backend/src/agent_platform/api/main.py` — wire DiscoveryProvider
- `backend/src/agent_platform/tools/capability_tools.py` — use discover internally
- `prompts/default.md` — document discover tool

## Risks & Decisions
- Parallel search across 5 sources may be slow — accept since discover is called once per task, not per iteration
- Score normalization: embedding similarity scores from different sources may not be directly comparable. Use raw cosine similarity and let ranking sort them.
- Memory search returns MemoryEntry objects; knowledge returns DocumentChunk — need to normalize to unified format
