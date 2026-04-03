---
name: email-subject
description: Generate professional email subject line options from email body text, including a tone tag (formal, casual, or urgent) for each option
parameters:
  type:
    type: string
  properties:
    body: {'type': 'string', 'description': 'The email body text to generate subject lines for'}
  required:
    type: string
---

Generate 3 professional email subject line options for this email. For each option, include a tone tag chosen from: formal, casual, urgent.

Return the result as a numbered list in this format:
1. [tone] Subject line
2. [tone] Subject line
3. [tone] Subject line

Email:

{{body}}