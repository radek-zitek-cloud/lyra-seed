# Getting Started with Lyra Agent Platform

## What is Lyra

Lyra is a self-evolving multi-agent platform where LLM-powered agents can converse with humans, use tools, spawn sub-agents, remember across sessions, create new capabilities, and orchestrate complex tasks. Everything is observable in real-time via a web UI.

## Prerequisites

- Python 3.12+ with uv (package manager)
- Node.js 18+ with npm
- An OpenRouter API key (provides access to all major LLM models)

## Installation

Clone the repository, copy the example configs, set your API key, install dependencies, and start:

```bash
git clone https://github.com/radek-zitek-cloud/lyra-seed.git
cd lyra-seed
cp .env.example .env
cp lyra.config.example.json lyra.config.json
# Edit .env — set LYRA_OPENROUTER_API_KEY
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
just dev
```

Backend runs at http://localhost:8000, frontend at http://localhost:3000.

## First Steps

1. Open http://localhost:3000 in your browser
2. Type a name and click CREATE to create your first agent
3. Click the agent to open its detail page
4. Type a message in the prompt bar and press SEND
5. Watch the event timeline on the right update in real-time

## Key Concepts

### Agents

An agent is an LLM-powered entity with its own conversation, memory, and tool access. Agents can be created via the UI or API. Each agent has a configuration (model, temperature, HITL policy, tool access) that can come from template files.

### Tools

Tools are capabilities agents can use: filesystem operations, shell commands, memory management, sub-agent spawning, orchestration, skills, and more. The LLM decides which tools to call based on the conversation.

### Memory

Agents have persistent memory that spans conversations. Facts are automatically extracted and stored. Agents can explicitly remember, recall, and forget information. Memories are searchable via semantic similarity.

### Templates

Pre-defined agent roles (researcher, writer, coder, critic, etc.) with specialized system prompts and configurations. Use templates when spawning sub-agents to give them appropriate behavior.

### Skills

Reusable prompt templates that agents can discover, create, test, and version. Skills are .md files that get registered as tools.

### Orchestration

For complex tasks, agents can decompose work into subtasks and execute them sequentially, in parallel, or as a pipeline. Results are automatically synthesized.

### Knowledge Base

The platform can ingest markdown documents into a semantic knowledge base. Agents search it to ground their responses in documented information rather than relying solely on training data.
