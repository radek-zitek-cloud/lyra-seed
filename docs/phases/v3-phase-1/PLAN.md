# V3 Phase 1 — Plan

## Phase Reference
- **Version:** V3
- **Phase:** 1
- **Title:** Tool Creation — Skills
- **Roadmap Section:** V3P1

## Prerequisites
- [x] V2 Phase 7: Skills — Filesystem-Based Prompt Macros — COMPLETE

## Deliverables Checklist
- [ ] 1.1: `test_skill` tool — dry-run a skill template without making it permanent
- [ ] 1.2: Skill versioning — `update_skill` creates new version, retains old as `{name}.v{n}.md`
- [ ] 1.3: `create_skill` validates name (no special chars, no conflicts with core tools)
- [ ] 1.4: Semantic skill search — `list_skills(query=...)` finds relevant skills via embedding similarity
- [ ] 1.5: Skill deduplication — `create_skill` checks for semantically similar existing skills before creating
- [ ] 1.6: Update system prompt to document new tools and semantic search

## Implementation Steps

### 1. Add test_skill tool
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- `test_skill` tool: dry-runs a skill template and evaluates the result against the skill's description
- Two LLM calls:
  1. **Execution call:** expand template with test arguments, run LLM sub-call using the agent's model — produces the skill output
  2. **Evaluation call:** send the skill description + the output to the LLM with a system prompt asking "Does this output fulfill the skill's purpose?" — uses the cheaper `orchestrationModel`. Returns structured verdict: PASS/FAIL with reasoning.
- Parameters: `template` (required), `description` (required — what the skill is supposed to do), `test_args` (JSON string of test arguments)
- Returns: `{ "output": "...", "verdict": "PASS|FAIL", "reasoning": "..." }`
- No file created — this is a quality gate before `create_skill`
- Evaluation prompt stored in `prompts/system/evaluate_skill.md` (externalized, editable)
- Registered alongside `list_skills` and `create_skill`

### 2. Add skill versioning via update_skill
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- `update_skill` tool: updates an existing skill by writing a new version
- Before overwriting, renames the current file to `{name}.v{n}.md` where `n` is the next available version number
- Writes the new content to `{name}.md`
- Reloads the skill provider
- Parameters: `name` (required), `description`, `template` (required), `parameters` (JSON string)
- Rejects if the skill doesn't exist (use `create_skill` for new ones)

### 3. Improve create_skill validation
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- Validate skill name: alphanumeric, hyphens, and underscores only
- Reject names that conflict with built-in tools: `list_skills`, `create_skill`, `test_skill`, `update_skill`, `remember`, `recall`, `forget`, `spawn_agent`, etc.
- Already rejects duplicate names (existing behavior)

### 4. Add semantic search to list_skills
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- Accept optional `query` parameter on `list_skills`
- When `query` is provided: embed the query, compute cosine similarity against cached skill description embeddings, return top matches ranked by relevance
- When `query` is omitted: return all skills (current behavior)
- Skill embeddings computed on load and refreshed on create/update/reload
- Uses the platform's embedding provider (injected via constructor)

### 5. Add semantic deduplication to create_skill
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- Before creating, embed the new skill's description
- Compare against existing skill description embeddings using cosine similarity
- If similarity exceeds threshold (configurable, default 0.85): reject with error listing the similar skill
- Reuses the same embedding cache as list_skills search

### 6. Wire embedding provider
**Files:** `backend/src/agent_platform/api/main.py`

- Pass `embedding_provider` to SkillProvider constructor
- SkillProvider stores it and uses for search/dedup
- If embedding provider is not available (e.g., in tests), search and dedup degrade gracefully (return all / skip check)

### 7. Update system prompt
**Files:** `prompts/default.md`

- Document `test_skill`, `update_skill` tools
- Document `list_skills(query=...)` for semantic search
- Add guidance on workflow: search → test → create

## File Manifest
- `backend/src/agent_platform/tools/skill_provider.py` — add test_skill, update_skill, search, dedup, validation
- `backend/src/agent_platform/api/main.py` — pass embedding provider to SkillProvider
- `backend/tests/smoke/test_v3_phase_1.py` — smoke tests
- `prompts/system/evaluate_skill.md` — evaluation prompt for test_skill
- `prompts/default.md` — document new tools

## Risks & Decisions
- Version files (`{name}.v1.md`, `{name}.v2.md`) are kept in the skills directory but not loaded as active skills — only `{name}.md` is the active version
- `test_skill` makes a real LLM call (mocked in tests) — there's a cost, but it's the only way to validate the template produces useful output
- Skill names validated with `^[a-zA-Z0-9_-]+$` regex
- Embedding cache is in-memory — recomputed on reload. Acceptable since skill counts are small (tens, not thousands)
- Dedup threshold 0.85 is intentionally high to avoid false positives — better to allow a near-duplicate than to block a legitimate new skill
- When embedding provider is unavailable (tests, offline), search returns all skills and dedup is skipped
