---
name: code-review
description: Review code for quality, bugs, and improvements
parameters:
  code:
    type: string
    description: The code to review
    required: true
  language:
    type: string
    description: Programming language (e.g. Python, TypeScript)
  focus:
    type: string
    description: Review focus (e.g. security, performance, readability)
---

Review the following {{language}} code. Focus on: {{focus}}.

Provide your review as:
1. **Issues** — bugs, logic errors, or security concerns (ranked by severity)
2. **Improvements** — suggestions for better code quality
3. **Positive** — what's done well

Be specific — reference line numbers or patterns, not vague advice.

```
{{code}}
```
