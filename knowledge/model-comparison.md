# LLM Model Comparison Guide

## Choosing the Right Model

This guide helps select the appropriate model for different tasks and budgets.

## By Task Type

### Complex Reasoning & Analysis

| Model | Quality | Cost | Speed |
|-------|---------|------|-------|
| Claude Opus 4.6 | Excellent | $5/$25 per M tok | Slow |
| GPT-5.4 | Excellent | $2.5/$15 per M tok | Medium |
| Gemini 3 Pro | Excellent | Varies | Medium |
| Llama 4 Maverick | Very Good | $0.1-0.5 self-hosted | Varies |

**Recommendation:** GPT-5.4 for best cost/quality ratio. Claude Opus for maximum quality.

### Code Generation

| Model | Quality | Cost | Notes |
|-------|---------|------|-------|
| Claude Opus 4.6 | Excellent | High | Best for complex multi-file changes |
| Claude Sonnet 4.6 | Very Good | Medium | Good daily driver for coding |
| Codestral (Mistral) | Very Good | Medium | Specialized for code |
| GPT-5.4 | Very Good | Medium | Strong all-rounder |

**Recommendation:** Claude Sonnet 4.6 for everyday coding, Opus for complex architecture.

### High-Volume Processing

| Model | Quality | Cost | Speed |
|-------|---------|------|-------|
| GPT-5.4 Mini | Good | $0.75/$4.5 | Fast |
| GPT-5.4 Nano | Adequate | $0.20/$1.25 | Very Fast |
| Claude Haiku 4.5 | Good | $1/$5 | Fast |
| Gemini 3 Flash | Good | $0.50/$3 | Very Fast |

**Recommendation:** GPT-5.4 Mini for quality-sensitive bulk work. Nano or Flash for classification/extraction.

### Long Document Processing

| Model | Context | Notes |
|-------|---------|-------|
| Gemini 3 Pro | 2M tokens | Largest context window |
| Claude Opus 4.6 | 200K-1M | Extended context available |
| GPT-5.4 | 128K | Sufficient for most use cases |

**Recommendation:** Gemini for extremely long documents, Claude for long + high quality.

## Cost Optimization Strategies

### Tiered Model Usage

Use different models for different parts of an agentic workflow:
- **Agent reasoning:** Full model (GPT-5.4, Claude Sonnet)
- **Orchestration subtasks:** Mini/Nano model
- **Fact extraction:** Mini model
- **Embeddings:** Dedicated embedding model (text-embedding-3-large)

### Self-Hosting

For high-volume workloads, self-hosting Llama 4 or Mistral Nemo can reduce costs by 5-10x compared to API calls. Requires GPU infrastructure.

### Caching

Cache embedding results for repeated queries. Cache LLM responses for deterministic operations (extraction prompts with same input should produce same output).

## OpenRouter as Abstraction Layer

OpenRouter provides a single API endpoint for all major model providers. Benefits:
- Switch models without code changes
- Unified billing across providers
- Automatic fallback if a provider is down
- Consistent API format across models

The Lyra platform uses OpenRouter as its default LLM provider, making it easy to experiment with different models by changing `defaultModel` in `lyra.config.json`.
