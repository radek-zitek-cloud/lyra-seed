# Mistral AI Models

## Current Model Lineup

Mistral AI, based in Paris, produces efficient models that punch above their weight class.

### Mistral Large

- Mistral's flagship model
- Best for: complex reasoning, multilingual (strong in European languages), code
- Context window: 128K tokens
- Strengths: strong performance relative to model size, excellent for European language tasks
- Available via Mistral API and OpenRouter

### Codestral

- Specialized code generation model
- Best for: code completion, code generation, refactoring, debugging
- Trained specifically on code and technical content
- Supports 80+ programming languages
- Available as IDE plugin (VS Code, JetBrains) and API

### Mistral Small

- Cost-efficient general-purpose model
- Best for: classification, extraction, simple generation
- Good quality-to-cost ratio for high-volume tasks

### Mistral Nemo

- Open-weight 12B parameter model
- Best for: self-hosting, edge deployment, fine-tuning
- Released under Apache 2.0 license
- Can run on a single GPU

## Key Differentiators

### European AI

Mistral is a European company subject to EU regulations. This matters for organizations with data sovereignty requirements. They offer EU-hosted endpoints.

### Efficiency

Mistral models are known for achieving strong benchmark results with fewer parameters than competitors. Their mixture-of-experts architecture activates only a fraction of total parameters per token.

### Function Calling

Mistral models support function calling compatible with the OpenAI format. Works with standard tooling and frameworks.

## API Access

- Direct: `api.mistral.ai`
- Via OpenRouter: `openrouter.ai` (prefix with `mistralai/`)
- Self-hosted: Nemo available on Hugging Face
