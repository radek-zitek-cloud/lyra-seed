---
name: executive-summary
description: Condense technical content into a brief executive summary for non-technical or time-pressed readers
parameters:
  content:
    type: string
    description: The technical content to summarize
    required: true
  max_sentences:
    type: string
    description: Maximum number of sentences (default 3-5)
---

Write an executive summary of the following technical content.

**Rules:**
- Maximum {{max_sentences}} sentences
- Lead with the most important conclusion or finding
- Use plain language — avoid jargon unless essential, and briefly define any that you use
- Focus on the "so what" — why does this matter, what should someone do about it
- Be specific — include key numbers, names, or outcomes rather than vague statements

**Content:**

{{content}}
