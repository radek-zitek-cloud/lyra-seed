# Anthropic Claude Models

## Claude 4.6 (Opus, Sonnet)

Released mid-2025. The Claude 4.6 family represents Anthropic's most capable models.

### Claude Opus 4.6

- Anthropic's flagship reasoning model
- Best for: complex analysis, code generation, long-context reasoning, multi-step problem solving
- Context window: 200K tokens (1M in extended context mode)
- Pricing: $5.00/M input, $25.00/M output tokens
- Model ID: `claude-opus-4-6` or `anthropic/claude-opus-4-6` on OpenRouter
- Strengths: exceptional at following complex instructions, code quality, nuanced reasoning
- Weaknesses: slower than smaller models, higher cost per token

### Claude Sonnet 4.6

- Mid-tier model balancing capability and cost
- Best for: everyday coding, writing, analysis, customer-facing applications
- Context window: 200K tokens
- Pricing: $3.00/M input, $15.00/M output tokens
- Model ID: `claude-sonnet-4-6` or `anthropic/claude-sonnet-4-6` on OpenRouter
- Strengths: good balance of quality and speed, strong at code and structured output
- Competitive with OpenAI GPT-5.4

### Claude Haiku 4.5

- Fastest and cheapest model in the Claude family
- Best for: high-volume tasks, classification, extraction, simple Q&A
- Context window: 200K tokens
- Pricing: $1.00/M input, $5.00/M output tokens
- Model ID: `claude-haiku-4-5` or `anthropic/claude-haiku-4-5` on OpenRouter
- Strengths: very fast response times, cost-efficient for bulk operations
- Suitable for fact extraction, summarization, and tool-calling in agentic workflows

## Key Features Across Claude Models

### Extended Thinking

Claude models support "extended thinking" mode where the model reasons step-by-step before producing a final answer. Useful for math, logic, and complex problem decomposition. Available on Opus and Sonnet.

### Tool Use

All Claude models support function calling / tool use via the Anthropic API. Tools are defined as JSON schemas and the model can decide when and which tools to call. Supports parallel tool calling.

### Computer Use

Claude models can interact with computer interfaces (screenshots, mouse, keyboard) via the computer use capability. Primarily available on Sonnet and Opus.

### System Prompts

Claude models support system prompts for persona definition, behavioral guidelines, and context setting. System prompts are processed as instructions the model follows throughout the conversation.

## API Access

- Direct: `api.anthropic.com`
- Via OpenRouter: `openrouter.ai` (prefix model IDs with `anthropic/`)
- SDKs: Python (`anthropic`), TypeScript (`@anthropic-ai/sdk`)
