# Lyra Platform Configuration

## Configuration Layers

Lyra uses a four-level configuration resolution chain. Most specific wins:

1. `prompts/{agent-name}.json` — per-agent override
2. `prompts/default.json` — default for all agents
3. `lyra.config.json` — platform-wide settings
4. Hardcoded defaults — fallback in code

## Environment Variables (.env)

Secrets and server bind config only. Prefix: `LYRA_`.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| LYRA_OPENROUTER_API_KEY | Yes | — | API key for LLM and embedding calls |
| LYRA_HOST | No | 0.0.0.0 | Backend bind address |
| LYRA_PORT | No | 8000 | Backend bind port |
| LYRA_CORS_ORIGINS | No | localhost:3000 | Allowed frontend origins |

Non-LYRA_ variables can also be in .env (e.g., FIRECRAWL_API_KEY, MICROBLOG_API_KEY). They are loaded into os.environ at startup.

## Platform Config (lyra.config.json)

### Directories

| Field | Default | Purpose |
|-------|---------|---------|
| dataDir | ./data | SQLite databases and memory storage |
| systemPromptsDir | ./prompts | Agent prompt templates and configs |
| skillsDir | ./skills | Skill .md files |
| mcpServersDir | ./mcp-servers | Agent-managed MCP server configs |
| knowledgeDir | ./knowledge | Knowledge base .md documents |

### Models

| Field | Default | Purpose |
|-------|---------|---------|
| defaultModel | openai/gpt-4.1-mini | Main LLM for agent reasoning |
| embeddingModel | openai/text-embedding-3-large | For memory and knowledge search |
| summaryModel | openai/gpt-4.1-nano | For context compression |
| extractionModel | openai/gpt-4.1-nano | For automatic fact extraction |
| orchestrationModel | null | For orchestration subtasks (falls back to agent model) |

### MCP Servers

MCP servers provide tools to agents. Defined in lyra.config.json under mcpServers:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "fast-filesystem-mcp"],
      "env": {"CREATE_BACKUP_FILES": "true"}
    },
    "shell": {
      "command": "uvx",
      "args": ["mcp-shell-server"],
      "env": {"ALLOW_COMMANDS": "ls,cat,git,python"}
    }
  }
}
```

Environment variables in MCP config can reference .env values: `"API_KEY": "${MY_API_KEY}"`.

### Tuning Parameters

| Section | Fields | Purpose |
|---------|--------|---------|
| retry | max_retries, base_delay, max_delay, timeout | LLM API retry behavior |
| hitl | timeout_seconds | HITL approval timeout |
| memoryGC | prune_threshold, max_entries, dedup_threshold | Memory cleanup |
| context | max_tokens, memory_top_k | Context window management |
| maxSubtasks | integer | Max orchestration subtasks |
| maxSpawnDepth | integer | Max sub-agent nesting depth |

## Agent Config Files

Each agent can have a `prompts/{name}.json` config and `prompts/{name}.md` system prompt. When an agent is created with a name matching a file, that config is loaded.

### Key Agent Config Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| model | string | from platform | LLM model |
| temperature | float | 0.7 | Creativity vs precision |
| max_iterations | int | 10 | Max tool-call loop iterations |
| hitl_policy | string | never | HITL approval: always_ask, dangerous_only, never |
| auto_extract | bool | true | Automatic fact extraction |
| allowed_mcp_servers | list/null | null (all) | Which MCP servers agent can access |
| allowed_tools | list | [] (all) | Explicit tool whitelist |
| orchestration_model | string | from platform | Model for orchestration calls |
| max_subtasks | int | 10 | Max orchestration subtasks |

### Tool Scoping

Control which tools an agent sees:
- `allowed_mcp_servers: null` — all MCP servers (default)
- `allowed_mcp_servers: []` — no MCP servers (pure reasoning)
- `allowed_mcp_servers: ["filesystem"]` — only filesystem tools
- `allowed_tools: ["remember", "recall"]` — strict whitelist

Core tools (memory, spawner, orchestration, skills) are never filtered by MCP scoping. Only `allowed_tools` can filter them.

## Config Editor UI

The web UI at /config provides a file editor for all configuration:
- Platform Config (lyra.config.json, .env)
- Agent Configs (prompts/*.json)
- Agent Prompts (prompts/*.md)
- System Prompts (prompts/system/*.md)
- Skills (skills/*.md)
- MCP Servers (mcp-servers/*.json)

Features: save/cancel, delete with confirmation, cursor-aware context help, reload config button, restart server button.
