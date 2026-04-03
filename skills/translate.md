---
name: translate
description: Translate text to a target language
parameters:
  text:
    type: string
    description: The text to translate
    required: true
  language:
    type: string
    description: Target language (e.g. Spanish, French, Czech)
    required: true
---

Translate the following text to {{language}}. Preserve the original meaning, tone, and formatting. If the text contains technical terms, keep them accurate in the target language.

{{text}}
