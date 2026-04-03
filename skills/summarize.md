---
name: summarize
description: Summarize text into concise bullet points
parameters:
  text:
    type: string
    description: The text to summarize
    required: true
  bullet_count:
    type: string
    description: Number of bullet points (default 3-5)
---

Summarize the following text into {{bullet_count}} concise bullet points. Each bullet should capture a key point. Be specific and avoid vague generalizations.

{{text}}
