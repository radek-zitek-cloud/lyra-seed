---
name: meeting-notes-to-action-items
description: Convert meeting notes into clear action items with owners and deadlines
parameters:
  type:
    type: string
  properties:
    notes: {'type': 'string', 'description': 'The meeting notes to convert into action items'}
  required:
    type: string
---

Convert the following meeting notes into a concise action-item list.

For each action item, include:
- Action
- Owner (if mentioned, otherwise "Unassigned")
- Deadline (if mentioned, otherwise "No deadline specified")

Meeting notes:

{{notes}}