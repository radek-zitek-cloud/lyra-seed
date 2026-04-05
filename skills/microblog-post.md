---
name: microblog-post
description: Format content into a microblog post with markdown and hashtags, max 5000 characters
parameters:
  topic:
    type: string
    description: The topic or title of the post
    required: true
  content:
    type: string
    description: The raw content, research, or draft to turn into a post
    required: true
  audience:
    type: string
    description: Target audience (default developers)
  tone:
    type: string
    description: Writing tone — casual, professional, tutorial (default casual-professional)
---

Write a microblog post about **{{topic}}** based on the following content.

**Constraints:**
- Maximum 5000 characters total (this is a hard limit — count carefully)
- Text-only, supports markdown formatting
- Include 2-5 relevant #hashtags at the end
- No images or embeds

**Audience:** {{audience}}
**Tone:** {{tone}}

**Structure:**
1. Hook — an opening that grabs attention
2. Core content — the main insight or explanation, concise and clear
3. Takeaway — what the reader should remember
4. Hashtags

**Source content:**

{{content}}
