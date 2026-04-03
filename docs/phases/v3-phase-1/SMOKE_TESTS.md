# V3 Phase 1 — Smoke Tests

## Test Environment
- Prerequisites: V2P7 complete, all prior smoke tests passing
- LLM calls: always mocked
- Embedding calls: mocked with deterministic fake vectors
- External APIs: never called

## Backend Smoke Tests

### ST-V3-1.1: test_skill dry-runs and evaluates a template
- **Validates:** Two-call flow: execution + evaluation, no file creation
- **Method:** Call test_skill with template, description, and test args. Mock LLM to return output on first call and PASS verdict on second call.
- **Checks:**
  - Template expanded correctly (placeholders replaced)
  - First LLM call: expanded prompt (execution)
  - Second LLM call: evaluation prompt with description + output (uses orchestration model)
  - Result contains output, verdict (PASS/FAIL), and reasoning
  - No file created in skills directory

### ST-V3-1.2: update_skill versions an existing skill
- **Validates:** Versioning on update
- **Method:** Create a skill, then update it
- **Checks:**
  - Original file renamed to `{name}.v1.md`
  - New content written to `{name}.md`
  - Updated skill immediately available via list_tools
  - Version file exists on disk
  - Version file not loaded as an active skill

### ST-V3-1.3: update_skill rejects nonexistent skill
- **Validates:** Update requires existing skill
- **Checks:**
  - Calling update_skill for a name that doesn't exist returns error
  - Error message says to use create_skill instead

### ST-V3-1.4: Multiple updates increment version numbers
- **Validates:** Sequential versioning
- **Method:** Create a skill, update it 3 times
- **Checks:**
  - Files exist: `{name}.v1.md`, `{name}.v2.md`, `{name}.v3.md`
  - Active `{name}.md` has the latest content
  - Only the active version loaded as a tool

### ST-V3-1.5: create_skill validates name format
- **Validates:** Name validation
- **Checks:**
  - Valid names accepted: `my_skill`, `code-review`, `summarize2`
  - Invalid names rejected: `my skill` (space), `a/b` (slash), `hello!` (special char)
  - Error message explains allowed format

### ST-V3-1.6: create_skill rejects core tool names
- **Validates:** Name conflict prevention
- **Checks:**
  - Names like `remember`, `spawn_agent`, `list_skills`, `create_skill` rejected
  - Error message explains the name is reserved

### ST-V3-1.7: test_skill uses agent's model
- **Validates:** Model propagation
- **Method:** Call test_skill with agent_id, check LLM config
- **Checks:**
  - LLM sub-call uses the agent's configured model

### ST-V3-1.8: Version files excluded from skill loading
- **Validates:** Only active versions loaded
- **Method:** Create skills directory with `foo.md`, `foo.v1.md`, `foo.v2.md`
- **Checks:**
  - Only `foo` appears in list_tools (not `foo.v1` or `foo.v2`)

### ST-V3-1.9: list_skills semantic search
- **Validates:** Query-based skill discovery
- **Method:** Load 3 skills with distinct descriptions, mock embedding provider with distinguishable vectors, call list_skills with a query
- **Checks:**
  - Returns skills ranked by relevance to query
  - Most relevant skill is first
  - Without query parameter, returns all skills (existing behavior)

### ST-V3-1.10: create_skill deduplication
- **Validates:** Semantic duplicate detection
- **Method:** Create a skill, then try to create another with a very similar description, mock embeddings to return high similarity
- **Checks:**
  - Second create rejected with error naming the similar existing skill
  - Sufficiently different descriptions are allowed through

### ST-V3-1.11: Graceful degradation without embedding provider
- **Validates:** Works without embeddings
- **Method:** Create SkillProvider without embedding_provider
- **Checks:**
  - list_skills without query works (returns all)
  - list_skills with query returns all (no filtering, no crash)
  - create_skill works (no dedup check, no crash)
