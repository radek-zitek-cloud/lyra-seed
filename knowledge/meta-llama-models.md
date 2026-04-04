# Meta Llama Models

## Llama 4 Family

Released early 2026. Meta's open-weight model family, available for commercial use.

### Llama 4 Maverick

- Large multimodal model
- Best for: complex reasoning, multilingual, code generation
- Parameters: 400B+ (mixture of experts)
- Context window: 128K tokens
- Strengths: competitive with GPT-5.4 and Claude Sonnet on benchmarks
- Open weights: downloadable, self-hostable, fine-tunable
- Available on: Hugging Face, Together AI, Fireworks, OpenRouter

### Llama 4 Scout

- Mid-tier model optimized for efficiency
- Parameters: ~100B (mixture of experts)
- Context window: 128K tokens
- Best for: general-purpose tasks, coding, analysis
- Significantly cheaper to run than Maverick
- Good self-hosting option for teams with GPU infrastructure

### Llama 4 Nano

- Smallest Llama 4 variant
- Designed for edge deployment and mobile devices
- Can run on consumer hardware

## Key Differentiators

### Open Weights

Unlike OpenAI and Anthropic, Meta releases Llama weights under a permissive license. Organizations can:
- Self-host for data privacy
- Fine-tune on domain-specific data
- Run without API costs (pay only for compute)
- Deploy on-premises or in private clouds

### Multilingual

Llama 4 supports 100+ languages out of the box, making it strong for international applications.

### Cost Advantage

When self-hosted, Llama models can be significantly cheaper than API-based models. Typical cost: $0.10-0.50/M tokens on cloud GPU providers vs $2-5/M for commercial APIs.

## API Access

- Self-hosted: download from `llama.meta.com` or Hugging Face
- Hosted APIs: Together AI, Fireworks, Groq, OpenRouter
- Model IDs vary by provider (e.g., `meta-llama/llama-4-maverick` on OpenRouter)
