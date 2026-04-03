# V2 Phase 7 — Plan

## Phase Reference
- **Version:** V2
- **Phase:** 7
- **Title:** Skills — Filesystem-Based Prompt Macros
- **Roadmap Section:** V2P7

## Prerequisites
- [x] V2 Phase 4: Per-Agent Tool Scoping — COMPLETE

## Deliverables Checklist
- [ ] 7.1: Skill file format — `.md` files with YAML frontmatter in `skills/` directory
- [ ] 7.2: `SkillProvider` implementing `ToolProvider` — scans directory, registers skills as tools
- [ ] 7.3: Skill execution — template expansion + LLM sub-call using calling agent's model
- [ ] 7.4: `create_skill` tool — agents create new skills at runtime (writes `.md` file)
- [ ] 7.5: `list_skills` and `get_skill` API endpoints (read-only, replacing macro CRUD)
- [ ] 7.6: Remove database-backed macro system (SqliteMacroRepo, macro_routes, PromptMacroProvider)
- [ ] 7.7: Configurable `skillsDir` in `lyra.config.json`
- [ ] 7.8: Starter skills — summarize, translate, code-review
- [ ] 7.9: Update existing tests that reference the old macro system
- [ ] 7.10: Update documentation (CONFIGURATION_GUIDE.md, default.md, prompts/README.md)

## Implementation Steps

### 1. Create skill file format and parser
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- Parse `.md` files: split on `---` to extract YAML frontmatter and template body
- Frontmatter fields: `name`, `description`, `parameters` (dict with type/description/required)
- Convert parameters dict to JSON Schema for tool registration
- Body is the template with `{{parameter}}` placeholders

### 2. Implement SkillProvider
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- `SkillProvider(skills_dir, llm_provider)` — scans directory on init
- `list_tools()` — returns skills as Tool objects (tool_type=PROMPT_MACRO, source="skill")
- `call_tool()` — expands template, makes LLM sub-call
- Use calling agent's model via `agent_id` injection (look up agent config from repo)
- `reload()` — re-scan directory (for runtime skill creation)

### 3. Implement create_skill tool
**Files:** `backend/src/agent_platform/tools/skill_provider.py`

- `create_skill` tool registered alongside skills
- Parameters: name, description, parameters (dict), template
- Writes a new `.md` file to skills directory with proper frontmatter
- Calls `reload()` to make it immediately available
- Validates name doesn't conflict with existing tools

### 4. Add list_skills and get_skill API endpoints
**Files:** `backend/src/agent_platform/api/skill_routes.py`

- `GET /skills` — list all loaded skills (name, description, parameters)
- `GET /skills/{name}` — get a specific skill with its template
- Read-only — no create/update/delete via API (agents use create_skill tool, editing is via filesystem)

### 5. Remove old macro system
**Files:** Remove/modify multiple files

- Delete `backend/src/agent_platform/db/sqlite_macro_repo.py`
- Delete `backend/src/agent_platform/api/macro_routes.py`
- Remove `PromptMacroProvider` from `prompt_macro.py` (keep the `PromptMacro` model temporarily if tests need it, or remove entirely)
- Update `main.py` — replace macro_provider with skill_provider
- Update `_deps.py` — remove macro_repo/macro_provider, add skill_provider
- Update `main.py` shutdown — remove macro_repo.close()

### 6. Add skillsDir to platform config
**Files:** `backend/src/agent_platform/core/platform_config.py`

- Add `skillsDir: str = "./skills"` to `PlatformConfig`
- Resolve relative to project root (same as `systemPromptsDir`)

### 7. Create starter skills
**Files:** `skills/summarize.md`, `skills/translate.md`, `skills/code-review.md`

### 8. Update existing tests
**Files:** `backend/tests/smoke/test_v1_phase_3.py`, `test_v1_phase_5.py`

- Replace macro repo/provider tests with skill provider tests
- Update app integration tests that reference macros

### 9. Wire into main.py
**Files:** `backend/src/agent_platform/api/main.py`

- Create SkillProvider with skills_dir from platform config
- Register with ToolRegistry
- Add `create_skill` to agent_id-injected tools in runtime.py
- Include skill_routes router

### 10. Update documentation
- `docs/CONFIGURATION_GUIDE.md` — add skillsDir section
- `prompts/default.md` — document skill tools
- `prompts/README.md` — update to reference skills

## File Manifest
**New:**
- `backend/src/agent_platform/tools/skill_provider.py` — SkillProvider + create_skill
- `backend/src/agent_platform/api/skill_routes.py` — read-only skill API
- `skills/summarize.md` — starter skill
- `skills/translate.md` — starter skill
- `skills/code-review.md` — starter skill
- `backend/tests/smoke/test_v2_phase_7.py` — smoke tests

**Removed:**
- `backend/src/agent_platform/db/sqlite_macro_repo.py`
- `backend/src/agent_platform/api/macro_routes.py`

**Modified:**
- `backend/src/agent_platform/api/main.py` — swap macro → skill provider
- `backend/src/agent_platform/api/_deps.py` — swap macro → skill deps
- `backend/src/agent_platform/core/runtime.py` — add create_skill to agent_id-injected tools
- `backend/src/agent_platform/core/platform_config.py` — add skillsDir
- `backend/tests/smoke/test_v1_phase_3.py` — update macro tests → skill tests
- `backend/tests/smoke/test_v1_phase_5.py` — update if needed
- `docs/CONFIGURATION_GUIDE.md` — add skills section
- `prompts/default.md` — document skills
- `prompts/README.md` — update references

## Risks & Decisions
- YAML frontmatter parsing — use a simple `---` split + `yaml.safe_load` rather than a full frontmatter library
- `create_skill` writes to filesystem — the skills directory must be writable at runtime
- Keeping `prompt_macro.py` PromptMacro model as internal implementation detail or removing entirely — remove if no test depends on it
- Backward compatibility — old macros in the database are lost. Since none exist in practice, this is fine.
