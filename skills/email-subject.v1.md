---
name: email-subject
description: Generate professional email subject line options from email body text
parameters:
  type:
    type: string
  properties:
    body: {'type': 'string', 'description': 'The email body text to generate subject lines for'}
  required:
    type: string
---

Generate 3 professional email subject line options for this email:

{{body}}