# V2 Phase 7 — Smoke Tests

## Test Environment
- Prerequisites: V2P4 complete, all prior smoke tests passing
- LLM calls: always mocked
- External APIs: never called

## Backend Smoke Tests

### ST-V2-7.1: Skill file parsing
- **Validates:** YAML frontmatter + template body parsing
- **Checks:**
  - Parses a `.md` file with `---` delimited frontmatter
  - Extracts name, description, parameters from frontmatter
  - Extracts template body (everything after second `---`)
  - Parameters converted to JSON Schema format

### ST-V2-7.2: SkillProvider loads skills from directory
- **Validates:** Directory scanning and tool registration
- **Method:** Create temp directory with skill files, initialize SkillProvider
- **Checks:**
  - Provider discovers all `.md` files in directory
  - `list_tools()` returns one Tool per skill file
  - Each tool has tool_type=PROMPT_MACRO, source="skill"
  - Tool names match frontmatter names

### ST-V2-7.3: SkillProvider executes a skill
- **Validates:** Template expansion and LLM sub-call
- **Method:** Mock LLM, call a skill with parameters
- **Checks:**
  - Template `{{parameter}}` placeholders expanded correctly
  - LLM called with expanded prompt
  - Result returned as ToolResult

### ST-V2-7.4: create_skill tool writes a new skill file
- **Validates:** Runtime skill creation
- **Method:** Call create_skill with name, description, parameters, template
- **Checks:**
  - New `.md` file created in skills directory
  - File has correct YAML frontmatter and template body
  - New skill immediately available via list_tools()
  - Duplicate name rejected

### ST-V2-7.5: Skills API endpoints
- **Validates:** GET /skills and GET /skills/{name}
- **Method:** Create app with skills directory, query endpoints
- **Checks:**
  - GET /skills returns list of loaded skills
  - GET /skills/{name} returns skill details including template
  - GET /skills/{name} returns 404 for unknown name

### ST-V2-7.6: Old macro system removed
- **Validates:** Database macro system is gone
- **Checks:**
  - `SqliteMacroRepo` class no longer importable
  - `/macros` API endpoints no longer exist (404)
  - No `prompt_macros` table in database

### ST-V2-7.7: PlatformConfig has skillsDir field
- **Validates:** Config field exists
- **Checks:**
  - `PlatformConfig.skillsDir` defaults to `"./skills"`
  - Parsed from lyra.config.json when present

### ST-V2-7.8: Starter skills exist
- **Validates:** Bundled skills
- **Checks:**
  - `skills/summarize.md` exists and parses correctly
  - `skills/translate.md` exists and parses correctly
  - `skills/code-review.md` exists and parses correctly
  - Each has valid frontmatter with name, description, parameters

### ST-V2-7.9: Skill execution uses agent's model
- **Validates:** Model propagation (not LLMConfig default)
- **Method:** Create agent with specific model, call a skill via runtime
- **Checks:**
  - LLM sub-call uses the agent's model, not the hardcoded default

### ST-V2-7.10: App integration — skills load at startup
- **Validates:** End-to-end wiring in create_app
- **Method:** Create app with skills directory containing a skill, query tools
- **Checks:**
  - Skill appears in GET /tools response
  - Skill appears in GET /skills response
  - Agent can call the skill via prompt
