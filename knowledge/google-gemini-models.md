# Google Gemini Models

## Gemini 3 Family

Released 2026. Google's latest generation of multimodal AI models.

### Gemini 3 Pro

- Google's most capable model
- Best for: complex reasoning, code, multimodal understanding, long documents
- Context window: 2M tokens (largest commercially available)
- Strengths: exceptional at long-context tasks, strong multimodal (text, image, video, audio)
- Available via Google AI Studio and Vertex AI

### Gemini 3 Flash

- Optimized for speed and cost
- Best for: high-volume applications, chatbots, summarization
- Context window: 1M tokens
- Pricing: $0.50/M input, $3.00/M output tokens (preview pricing)
- Model ID: `google/gemini-3-flash-preview` on OpenRouter
- Strengths: very fast, good quality-to-cost ratio
- Trade-offs: slightly lower reasoning capability than Pro

### Gemini 3 Flash Lite

- Smallest Gemini variant
- Best for: classification, extraction, simple tasks at scale
- Extremely cost-efficient

## Key Differentiators

### Long Context

Gemini's 2M token context window is the largest among major providers. This enables processing entire codebases, books, or large document collections in a single prompt without chunking.

### Native Multimodal

Gemini processes text, images, video, and audio natively in a single model. Unlike competitors that use separate vision models, Gemini handles all modalities in one architecture.

### Grounding with Google Search

Gemini can ground its responses using real-time Google Search results. This reduces hallucination for factual queries by citing current web sources.

### Code Execution

Gemini supports a built-in code execution sandbox. The model can write and run Python code within the conversation, returning actual execution results rather than predicting output.

## API Access

- Google AI Studio: `aistudio.google.com`
- Vertex AI: `cloud.google.com/vertex-ai`
- Via OpenRouter: `openrouter.ai` (prefix with `google/`)
