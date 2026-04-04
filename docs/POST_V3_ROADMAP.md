# Post-V3 Roadmap — Proposal

Based on a thorough codebase audit (171 smoke tests, 34 API endpoints, 7 tool providers, 25+ tools, 8 templates, 3 skills, 5 frontend pages) against the existing documentation.

---

## Current State Assessment

### What works well
- Complete agent lifecycle: create, prompt, spawn children, message, orchestrate, reflect
- Skill system with semantic search, test/validate, dedup, versioning
- MCP server management with HITL-gated deployment
- Per-agent tool scoping
- Memory with auto-extraction, decay, cross-agent sharing
- Config editor with context help, reload, restart
- Agent-drive testing framework (13 use cases)
- 171 smoke tests passing

### Technical debt identified

| Issue | Location | Severity |
|-------|----------|----------|
| `LLMConfig` default model is `minimax/minimax-m2.7` | `llm/models.py:48` | High — any LLMConfig without explicit model uses wrong model |
| `ToolType.PROMPT_MACRO` used for 28 non-macro tools | `tools/models.py` | Medium — misleading semantics |
| `_cosine_similarity()` duplicated in 3 files | skill_provider, template_provider, mcp_server_manager | Low — code duplication |
| `capability_tools.py` uses bare `LLMConfig(temperature=0.3)` | lines 275, 318 | High — hits minimax default for analyze + reflect |
| V3P3 marked "MOSTLY COMPLETE" but all tools exist | `ROADMAP.md` | Low — documentation accuracy |
| No smoke tests for V2P5 (graph UI) | missing test file | Low |
| `mcpServersDir` not in `lyra.config.json` | config file | Low — hardcoded default works |

### Documentation gaps

| Document | Issue |
|----------|-------|
| `REQUIREMENTS.md` | Missing V3P4 addendum |
| `ROADMAP.md` | V3P3 status needs update (tools were delivered in V3P4) |
| `CONFIGURATION_GUIDE.md` | Missing mcpServersDir, capability tools, template discovery |
| `README.md` | Test count outdated (says 152, actual 171), missing V3P4 |
| `prompts/README.md` | Missing capability-acquirer template |

---

## Proposed Post-V3 Phases

### V4 Phase 1: Technical Alignment & Cleanup

**Objective:** Fix the technical debt and inconsistencies before building more. A clean foundation makes everything that follows simpler and more reliable.

**Deliverables:**

1. **Fix LLMConfig default model**
   - Change `LLMConfig.model` default from `minimax/minimax-m2.7` to `None`
   - When `None`, the OpenRouter provider uses the platform's `defaultModel`
   - Eliminates the entire class of "wrong model" bugs
   - Fix `capability_tools.py` to pass model from agent config (same pattern as skills)

2. **ToolType enum cleanup**
   - Rename `PROMPT_MACRO` to `INTERNAL` or split into: `SKILL`, `MEMORY`, `AGENT`, `ORCHESTRATION`, `CAPABILITY`, `DISCOVERY`
   - Update all 28 references
   - Keep `MCP` as-is

3. **Extract shared utilities**
   - `_cosine_similarity()` → `agent_platform/core/math_utils.py`
   - `_build_skill_file()` pattern → shared if needed
   - Env var `${VAR}` resolution → shared utility

4. **Documentation sync**
   - Update REQUIREMENTS.md, ROADMAP.md, README.md, CONFIGURATION_GUIDE.md, prompts/README.md
   - All to reflect current state accurately

5. **Missing smoke tests**
   - Add test for V2P5 (graph UI) — at least verify the page renders

---

### V4 Phase 2: RAG Knowledge Base

**Objective:** Agents can ingest, index, and query `.md` knowledge base files. This is the foundation for the content pipeline — the agent needs to *read and understand* a corpus of documents before writing about them.

**Deliverables:**

1. **Knowledge base directory** (`knowledge/` or configurable)
   - `.md` files organized by topic
   - Loaded and indexed at startup
   - Hot-reload when files change

2. **Chunking and indexing**
   - Split documents into semantic chunks (heading-aware splitting)
   - Embed chunks into ChromaDB collection (separate from memories)
   - Metadata: source file, heading path, chunk position

3. **`search_knowledge(query, top_k)` tool**
   - Semantic search over the knowledge base
   - Returns relevant chunks with source attribution
   - Agent can ground its responses in documented knowledge

4. **`ingest_document(path)` tool**
   - Agent can add a new document to the knowledge base at runtime
   - Chunks, embeds, indexes

5. **Integration with `analyze_capabilities`**
   - Gap analysis includes "relevant knowledge" from the KB
   - Agent knows what domain knowledge is available

---

### V4 Phase 3: Unified Capability Discovery (BL-008)

**Objective:** Replace the current multi-call discovery pattern with a single `discover(query)` tool that searches across all capability sources. Foundation for on-demand tool schema.

**Deliverables:**

1. **`discover(query)` tool**
   - Single search across: skills, templates, MCP servers, tools, memories, knowledge base
   - Returns ranked results with type, name, description, relevance
   - Replaces the need for agents to call list_skills, list_templates, list_mcp_servers separately

2. **Unified embedding index**
   - All capability descriptions indexed in one ChromaDB collection
   - Updated on skill create/update, server add, template change

3. **On-demand tool schema (stretch goal)**
   - Send only core tools + `discover` in the initial LLM call
   - Agent calls `discover(query)` to find relevant tools
   - Discovered tools added to schema for subsequent iterations
   - Dramatically reduces per-call token cost

---

### V4 Phase 4: Content Pipeline Implementation

**Objective:** Build the technical content pipeline from `docs/USE_CASE_CONTENT_PIPELINE.md` as a working system. This is the proof of concept that ties everything together.

**Deliverables:**

1. **Content pipeline skills**
   - `executive-summary.md`, `blog-outline.md`, `seo-metadata.md`, `changelog-entry.md`

2. **Content pipeline templates**
   - `content-coordinator.json/md` — orchestrates the full pipeline
   - `tech-researcher.json/md` — reads codebase, produces findings
   - `blog-writer.json/md` — writes from research
   - `adr-writer.json/md` — Architecture Decision Records

3. **End-to-end test**
   - UC that exercises: coordinator → researcher (reads code) → writer → editor → critic → publish to microblog
   - Agent-drive test with execution report

4. **Knowledge base integration**
   - Researcher queries the knowledge base for existing documentation
   - Writer uses knowledge base as source material

---

### V4 Phase 5: Production Hardening

**Objective:** Make the platform reliable enough for regular use, not just demos.

**Deliverables:**

1. **Rate limiting and cost caps**
   - Per-agent cost limit (configurable)
   - Platform-wide daily cost cap
   - Rate limiting on LLM calls

2. **Error recovery**
   - Agent retry on LLM failures (exists but needs testing)
   - MCP server auto-reconnect on crash
   - Graceful degradation when services are unavailable

3. **Persistent agent sessions**
   - Agent can be paused and resumed across server restarts
   - Conversation history survives restart (already in SQLite)
   - Running tasks resumable

4. **Observability improvements**
   - Cost dashboard in UI
   - Agent session history (not just current)
   - Memory usage visualization

---

## Priority Recommendation

| Phase | Priority | Rationale |
|-------|----------|-----------|
| V4P1: Alignment & Cleanup | **Do first** | Fixes bugs (minimax model), reduces confusion, takes 1-2 hours |
| V4P2: RAG Knowledge Base | **High** | Required for content pipeline; enables grounded agent responses |
| V4P4: Content Pipeline | **High** | The concrete use case that proves the platform's value |
| V4P3: Unified Discovery | **Medium** | Nice optimization, not blocking |
| V4P5: Production Hardening | **Medium** | Important for regular use, not for demos |

**Suggested order:** V4P1 → V4P2 → V4P4 → V4P3 → V4P5

V4P1 is a quick cleanup. V4P2 + V4P4 together deliver the content pipeline — the most compelling demonstration of the platform. V4P3 and V4P5 are quality-of-life improvements that can come after.

---

## Backlog Items to Address

| Item | When |
|------|------|
| BL-001: delete_agent tool | V4P1 (quick add during cleanup) |
| BL-003: EventBus filtering | Defer — not blocking anything |
| BL-004: LLM-assisted HITL | Defer — interesting but not urgent |
| BL-007: Timeline scrubber | Defer — demo feature |
| BL-008: Unified RAG Discovery | V4P3 |
