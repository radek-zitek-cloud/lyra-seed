# Configuration Guide

This document covers all configuration surfaces in the Lyra Agent Platform.

---

## 1. Environment Variables (`.env`)

Secrets and server bind config. Everything else goes in `lyra.config.json`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LYRA_OPENROUTER_API_KEY` | Yes | — | OpenRouter API key for LLM and embedding calls |
| `LYRA_HOST` | No | `0.0.0.0` | Backend server bind address |
| `LYRA_PORT` | No | `8000` | Backend server bind port |

All variables use the `LYRA_` prefix. Loaded from `.env` in the project root via Pydantic Settings.

---

## 2. Platform Config (`lyra.config.json`)

Platform-wide settings loaded once at startup from the project root. Changes require a server restart.

### General

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dataDir` | string | `"./data"` | Directory for SQLite databases and memory storage |
| `systemPromptsDir` | string | `"./prompts"` | Directory containing agent prompt and config files |
| `skillsDir` | string | `"./skills"` | Directory containing skill `.md` files |
| `defaultModel` | string | `"openai/gpt-4.1-mini"` | Default LLM model for agent reasoning |
| `embeddingModel` | string | `"openai/text-embedding-3-large"` | Model for memory embeddings |

### Auxiliary Models

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `summaryModel` | string | `"openai/gpt-4.1-nano"` | Model for context compression summaries |
| `extractionModel` | string | `"openai/gpt-4.1-nano"` | Model for automatic fact extraction |
| `orchestrationModel` | string | `null` | Model for orchestration LLM calls (decomposition, subtask execution, synthesis). Falls back to agent's own model if not set |

### Orchestration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `maxSubtasks` | integer | `10` | Maximum subtasks the decomposer can produce per orchestration call |

### MCP Servers

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "fast-filesystem-mcp"],
      "env": { "CREATE_BACKUP_FILES": "true" }
    },
    "shell": {
      "command": "uvx",
      "args": ["mcp-shell-server"],
      "env": { "ALLOW_COMMANDS": "ls,cat,git,python" }
    }
  }
}
```

Each entry defines an MCP server that provides tools to agents:
- `command` — executable to run
- `args` — command-line arguments
- `env` — environment variables passed to the process

All MCP servers are connected at startup and their tools are discovered via the MCP protocol. By default, every agent sees every MCP server's tools. Use `allowed_mcp_servers` in agent config to restrict access (see section 3).

### Cost Tracking

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `modelCosts` | object | `{}` | Per-model costs as `[input_per_Mtok, output_per_Mtok]` in USD |
| `defaultModelCost` | array | `[1.0, 4.0]` | Fallback cost for models not in `modelCosts` |

### Retry

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `retry.max_retries` | integer | `3` | Maximum LLM API retry attempts |
| `retry.base_delay` | float | `1.0` | Base delay in seconds for exponential backoff |
| `retry.max_delay` | float | `30.0` | Maximum delay between retries |
| `retry.timeout` | float | `60.0` | Per-request timeout in seconds |

### HITL

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hitl.timeout_seconds` | float | `300` | How long an agent waits for human approval before timing out |

### Memory GC

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `memoryGC.prune_threshold` | float | `0.1` | Decay score below which memories are pruned |
| `memoryGC.max_entries` | integer | `500` | Maximum memories per agent before pruning |
| `memoryGC.dedup_threshold` | float | `0.9` | Similarity threshold for memory deduplication (0.0–1.0) |

### Context

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `context.max_tokens` | integer | `100000` | Maximum context tokens before compression |
| `context.memory_top_k` | integer | `5` | Number of relevant memories to inject per turn |

---

## 3. Agent Config Files (`prompts/{name}.json`)

Per-agent configuration overrides. Loaded when an agent is created via `POST /agents` with `name`. The resolution chain:

1. `prompts/{name}.json` — agent-specific config
2. `prompts/default.json` — fallback for all agents
3. Platform config (`lyra.config.json`) — fills remaining gaps
4. Hardcoded defaults in `AgentConfig`

### Available Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | from platform | LLM model for this agent's reasoning |
| `temperature` | float | `0.7` | LLM temperature |
| `max_iterations` | integer | `10` | Maximum tool-call loop iterations per prompt |
| `hitl_policy` | string | `"never"` | HITL approval policy: `"always_ask"`, `"dangerous_only"`, `"never"` |
| `auto_extract` | boolean | `true` | Automatically extract facts from conversations |
| `summary_model` | string | from platform | Model for context compression |
| `extraction_model` | string | from platform | Model for fact extraction |
| `orchestration_model` | string | from platform | Model for orchestration LLM calls |
| `max_subtasks` | integer | `10` | Maximum subtasks per orchestration call |
| `allowed_mcp_servers` | array | `null` | Which MCP servers this agent can access (see below) |
| `allowed_tools` | array | `[]` | Explicit tool name whitelist (see below) |
| `memory_sharing` | object | (per type) | Visibility defaults per memory type |
| `retry` | object | from platform | Per-agent retry overrides |
| `hitl` | object | from platform | Per-agent HITL timeout override |
| `memoryGC` | object | from platform | Per-agent memory GC overrides |
| `context` | object | from platform | Per-agent context overrides |

### Tool Scoping

**`allowed_mcp_servers`** controls which MCP servers' tools the agent can see:

| Value | Meaning |
|-------|---------|
| `null` (default) | Agent sees all MCP server tools |
| `[]` (empty array) | Agent sees no MCP server tools |
| `["filesystem"]` | Agent sees only filesystem server tools |
| `["filesystem", "shell"]` | Agent sees filesystem and shell tools |

Non-MCP tools (memory, sub-agent spawning, orchestration, prompt macros) are always available regardless of this setting.

**`allowed_tools`** is a strict whitelist of tool names:

| Value | Meaning |
|-------|---------|
| `[]` (default) | No restriction — agent sees all tools |
| `["remember", "recall"]` | Agent sees only those two tools |

When both are set, a tool must pass both filters.

### Memory Sharing

```json
{
  "memory_sharing": {
    "fact": "public",
    "procedure": "public",
    "tool_knowledge": "public",
    "domain_knowledge": "public",
    "preference": "private",
    "decision": "private",
    "episodic": "private",
    "outcome": "private"
  }
}
```

Controls default visibility when the agent stores a memory. Values: `"public"`, `"private"`, `"team"`.

### Example: Minimal worker

```json
{
  "temperature": 0.3,
  "max_iterations": 20,
  "hitl_policy": "never",
  "auto_extract": false,
  "allowed_mcp_servers": ["filesystem"]
}
```

### Example: Restricted research agent (no external tools)

```json
{
  "temperature": 0.7,
  "max_iterations": 10,
  "allowed_mcp_servers": [],
  "allowed_tools": ["remember", "recall", "forget", "orchestrate", "decompose_task"]
}
```

### Example: Full-access coder

```json
{
  "model": "openai/gpt-5.4",
  "temperature": 0.3,
  "max_iterations": 40,
  "hitl_policy": "never",
  "auto_extract": false
}
```

No `allowed_mcp_servers` set — gets access to all MCP servers.

---

## 4. Agent System Prompts (`prompts/{name}.md`)

Markdown files that define the agent's system prompt (personality, instructions, capabilities documentation). Resolution:

1. `prompts/{name}.md` — agent-specific prompt
2. `prompts/default.md` — fallback

The default prompt (`prompts/default.md`) documents:
- Memory system (injection, extraction, decay, tools)
- Sub-agent spawning (spawn_agent, wait_for_agent, etc.)
- Task orchestration (decompose_task, orchestrate, strategies, failure policies)

When creating a specialized agent, write a `{name}.md` that replaces or extends the default prompt.

---

## 5. Internal System Prompts (`prompts/system/*.md`)

System prompts used by internal platform components. Not agent-facing — these are sent as system messages when the platform makes its own LLM calls.

| File | Used by | Contains |
|------|---------|----------|
| `prompts/system/decompose_task.md` | TaskDecomposer | Instructions for breaking tasks into subtasks with JSON output format |
| `prompts/system/synthesize_results.md` | ResultSynthesizer | Instructions for combining subtask results into a unified response |
| `prompts/system/extract_facts.md` | FactExtractor | Instructions for extracting facts, decisions, and preferences from conversations |
| `prompts/system/summarize.md` | ContextManager | Instructions for summarizing old conversation messages |

These prompts support `{placeholder}` variables that the platform fills in at runtime (e.g., `{tools}`, `{task}`, `{results}`).

Editable without code changes — the platform loads them from disk at startup. Hardcoded fallback defaults exist in the code if files are missing.

---

## 6. Resolution Chain

Agent configuration follows a four-level resolution chain. Most specific wins:

```
prompts/{agent-name}.json   →  per-agent override
prompts/default.json         →  default for all agents
lyra.config.json             →  platform-wide config
hardcoded defaults           →  fallback in AgentConfig model
```

### How it works

1. Agent is created via `POST /agents` with a `name`
2. Platform looks for `prompts/{name}.json`, falls back to `prompts/default.json`
3. File config fields override `AgentConfig` defaults
4. For fields not set by file config, `lyra.config.json` values are applied
5. Any remaining fields use hardcoded Pydantic defaults

### What resolves from where

| Field | File config | Platform config | Hardcoded |
|-------|-------------|-----------------|-----------|
| `model` | `model` | `defaultModel` | `openai/gpt-4.1-mini` |
| `temperature` | `temperature` | — | `0.7` |
| `max_iterations` | `max_iterations` | — | `10` |
| `hitl_policy` | `hitl_policy` | — | `never` |
| `hitl_timeout_seconds` | `hitl.timeout_seconds` | `hitl.timeout_seconds` | `300` |
| `summary_model` | `summary_model` | `summaryModel` | `null` |
| `extraction_model` | `extraction_model` | `extractionModel` | `null` |
| `orchestration_model` | `orchestration_model` | `orchestrationModel` | `null` |
| `max_subtasks` | `max_subtasks` | `maxSubtasks` | `10` |
| `prune_threshold` | `memoryGC.prune_threshold` | `memoryGC.prune_threshold` | `0.1` |
| `max_context_tokens` | `context.max_tokens` | `context.max_tokens` | `100000` |
| `memory_top_k` | `context.memory_top_k` | `context.memory_top_k` | `5` |
| `allowed_mcp_servers` | `allowed_mcp_servers` | — | `null` (all) |
| `allowed_tools` | `allowed_tools` | — | `[]` (all) |
| `auto_extract` | `auto_extract` | — | `true` |
| `system_prompt` | `{name}.md` file | `default.md` file | `"You are a helpful assistant."` |

### Child agent resolution

When a parent agent spawns a child:

1. If a `template` is specified, load config from `prompts/{template}.json`
2. If template doesn't set a field, inherit from parent
3. Explicit overrides in `spawn_agent` arguments win over everything

For tool scoping specifically:
- Template's `allowed_mcp_servers` overrides parent's
- If template doesn't set it, child inherits parent's scope
- Same logic for `allowed_tools`

---

## 7. Skills (`skills/*.md`)

Skills are reusable prompt templates that register as tools. Each skill is a `.md` file with YAML frontmatter defining metadata and a body containing the prompt template.

### File format

```markdown
---
name: summarize
description: Summarize text into bullet points
parameters:
  text:
    type: string
    description: The text to summarize
    required: true
  bullet_count:
    type: string
    description: Number of bullet points (default 3-5)
---

Summarize the following text into {{bullet_count}} concise bullet points.

{{text}}
```

**Frontmatter fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Tool name agents use to call this skill |
| `description` | No | Shown to the LLM in the tool list |
| `parameters` | No | Parameter definitions (name → type, description, required) |

**Template body:** Everything after the second `---`. Use `{{parameter_name}}` for placeholders that get replaced with arguments at call time.

### How skills work

1. `SkillProvider` scans `skillsDir` at startup and registers each `.md` file as a tool
2. When an agent calls a skill, the template is expanded with the provided arguments
3. The expanded prompt is sent as a single LLM sub-call using the calling agent's model
4. The LLM response is returned as the tool result

### Agent tools for skills

| Tool | Description |
|------|-------------|
| `list_skills` | Returns all loaded skills with descriptions and parameters |
| `create_skill` | Creates a new skill `.md` file at runtime (immediately available) |
| Individual skills | Each loaded skill appears as a callable tool |

### API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /skills` | List all loaded skills |
| `GET /skills/{name}` | Get a skill with its template |

### Applying changes

Skills can be reloaded without a server restart using the **RELOAD CONFIG** button in the Config Editor UI, or via `POST /config/reload`.

---

## 8. Config Editor UI

The web-based config editor is available at `/config` in the frontend. It provides a unified interface for viewing and editing all configuration files.

### Sections

| Section | Contents | Editable | Deletable |
|---------|----------|----------|-----------|
| Platform Config | `lyra.config.json`, `.env` | Yes | No |
| Agent Configs | `prompts/*.json` | Yes | Yes |
| Agent Prompts | `prompts/*.md` | Yes | Yes |
| System Prompts | `prompts/system/*.md` | Yes | No |
| Skills | `skills/*.md` | Yes | Yes |

### Features

- **Inline editor** with monospace font and tab support
- **Save/Cancel** — save writes to disk immediately, cancel reverts to last saved state
- **Delete** with inline confirmation (protected for platform config and system prompts)
- **Context help** — a bar at the bottom shows documentation for the config key at the cursor position (works for JSON, `.env`, and skill YAML frontmatter)
- **Reload Config** — reloads skills from disk without restarting the server
- **Restart Server** — full server restart with inline confirmation and automatic reconnection polling

### API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /config/files` | List all config files grouped by category |
| `GET /config/file?path=...` | Read a file's content |
| `PUT /config/file` | Write/update a file |
| `DELETE /config/file?path=...` | Delete a file (agent configs, prompts, skills only) |
| `POST /config/reload` | Reload skills and refresh config |
| `POST /config/restart` | Restart the backend server |

### When to reload vs restart

| Change | Action needed |
|--------|---------------|
| Edited a skill `.md` file | Reload |
| Edited an agent prompt or config | No action (reloads per agent creation) |
| Edited `lyra.config.json` | Restart (loaded once at startup) |
| Changed MCP server configuration | Restart |
| Changed `.env` variables | Restart |
