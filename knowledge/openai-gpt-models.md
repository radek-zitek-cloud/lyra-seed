# OpenAI GPT Models

## GPT-5.4 Family

Released early 2026. OpenAI's latest production model family.

### GPT-5.4

- OpenAI's flagship model
- Best for: complex reasoning, creative writing, code generation, multimodal tasks
- Context window: 128K tokens
- Pricing: $2.50/M input, $15.00/M output tokens
- Model ID: `openai/gpt-5.4` on OpenRouter
- Strengths: strong general capability, good at following complex instructions
- Native multimodal: accepts images, audio, and text

### GPT-5.4 Mini

- Cost-optimized version of GPT-5.4
- Best for: summarization, extraction, translation, bulk processing
- Context window: 128K tokens
- Pricing: $0.75/M input, $4.50/M output tokens
- Model ID: `openai/gpt-5.4-mini` on OpenRouter
- Strengths: 3x cheaper than full model, good quality for most tasks
- Recommended for: fact extraction, context summarization, orchestration subtasks

### GPT-5.4 Nano

- Smallest and cheapest GPT-5.4 variant
- Best for: classification, simple extraction, formatting
- Context window: 128K tokens
- Pricing: $0.20/M input, $1.25/M output tokens
- Model ID: `openai/gpt-5.4-nano` on OpenRouter
- Strengths: extremely fast and cheap
- Trade-offs: lower quality on complex reasoning tasks

## GPT-5

- Previous generation flagship (early 2025)
- Still available but GPT-5.4 is preferred
- Model IDs: `openai/gpt-5`, `openai/gpt-5-mini`

## Key Features

### Function Calling

All GPT models support function calling with JSON schema tool definitions. Supports parallel tool calls. The model decides when to call tools based on the conversation context.

### Structured Output

GPT-5.4 supports guaranteed JSON output via `response_format: { type: "json_schema", json_schema: ... }`. Useful for ensuring parseable responses in agentic workflows.

### Vision

GPT-5.4 accepts images as input. Can analyze screenshots, diagrams, charts, and photographs. Useful for UI testing, document analysis, and visual reasoning.

### Embeddings

OpenAI provides dedicated embedding models:
- `text-embedding-3-large`: 3072 dimensions, best quality
- `text-embedding-3-small`: 1536 dimensions, cheaper

Used for semantic search, memory retrieval, and RAG applications. Available via OpenRouter.

## API Access

- Direct: `api.openai.com`
- Via OpenRouter: `openrouter.ai` (prefix model IDs with `openai/`)
- SDKs: Python (`openai`), TypeScript (`openai`)
