# V4 Phase 1 — Plan

## Phase Reference
- **Version:** V4
- **Phase:** 1
- **Title:** Technical Alignment & Cleanup
- **Roadmap Section:** POST_V3_ROADMAP.md

## Prerequisites
- [x] V3 Phase 4: Learning, Reflection & Capability Formalization — COMPLETE

## Deliverables Checklist
- [ ] 1.1: Fix LLMConfig default model — change from minimax to None, resolve from platform config
- [ ] 1.2: Fix capability_tools.py — analyze and reflect use agent's model, not LLMConfig default
- [ ] 1.3: ToolType enum — rename PROMPT_MACRO to INTERNAL (or add subtypes)
- [ ] 1.4: Extract shared utilities — cosine_similarity, env var resolution
- [ ] 1.5: Documentation sync — REQUIREMENTS.md, ROADMAP.md, README.md, CONFIGURATION_GUIDE.md, prompts/README.md
- [ ] 1.6: Mark V3P3 as COMPLETE in ROADMAP.md

## Implementation Steps

### 1. Fix LLMConfig default model
**Files:** `backend/src/agent_platform/llm/models.py`, `backend/src/agent_platform/llm/openrouter.py`

- Change `LLMConfig.model` default from `"minimax/minimax-m2.7"` to `None`
- In `OpenRouterProvider.complete()`, if `config.model is None`, use a platform default
- Pass platform's `defaultModel` to the OpenRouter provider at construction time
- This eliminates the entire class of "wrong model" bugs

### 2. Fix capability_tools.py model resolution
**Files:** `backend/src/agent_platform/tools/capability_tools.py`

- Accept `agent_repo` in constructor (same pattern as SkillProvider)
- In `_analyze` and `_reflect`, resolve model from agent config via agent_id
- Fallback to platform default if no agent_id

### 3. ToolType enum cleanup
**Files:** `backend/src/agent_platform/tools/models.py`, all files referencing ToolType.PROMPT_MACRO

- Rename `PROMPT_MACRO` to `INTERNAL`
- Update all 28 references across: skill_provider, template_provider, mcp_server_manager, capability_tools, agent_spawner, orchestration/tool_provider, memory_tools
- Keep `MCP` unchanged

### 4. Extract shared utilities
**Files:** new `backend/src/agent_platform/core/utils.py`

- Move `_cosine_similarity()` from 3 files to shared utility
- Move `${VAR}` env resolution to shared utility
- Update imports in skill_provider, template_provider, mcp_server_manager, main.py

### 5. Documentation sync
**Files:** Multiple docs

- REQUIREMENTS.md: add V3P4 addendum
- ROADMAP.md: mark V3P3 as COMPLETE, add V4 section header
- README.md: update test count (171), add V3P4, update status
- CONFIGURATION_GUIDE.md: add mcpServersDir, capability tools, template discovery
- prompts/README.md: add capability-acquirer template

### 6. Mark V3P3 complete
**Files:** `docs/ROADMAP.md`

- V3P3's deliverables were all delivered across V3P1, V3P2, and V3P4
- Update from "MOSTLY COMPLETE" to "COMPLETE"

## File Manifest
**New:**
- `backend/src/agent_platform/core/utils.py` — shared utilities
- `backend/tests/smoke/test_v4_phase_1.py` — smoke tests

**Modified:**
- `backend/src/agent_platform/llm/models.py` — LLMConfig default
- `backend/src/agent_platform/llm/openrouter.py` — model fallback
- `backend/src/agent_platform/tools/models.py` — ToolType rename
- `backend/src/agent_platform/tools/capability_tools.py` — model resolution
- `backend/src/agent_platform/tools/skill_provider.py` — shared imports
- `backend/src/agent_platform/tools/template_provider.py` — shared imports
- `backend/src/agent_platform/tools/mcp_server_manager.py` — shared imports
- `backend/src/agent_platform/api/main.py` — pass defaultModel to openrouter
- Multiple test files — ToolType.PROMPT_MACRO → INTERNAL
- Multiple docs — sync updates
