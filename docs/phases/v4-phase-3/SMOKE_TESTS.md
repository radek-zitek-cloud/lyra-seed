# V4 Phase 3 — Smoke Tests

## Test Environment
- Prerequisites: V4P2 complete, all prior smoke tests passing
- LLM calls: always mocked
- Embedding calls: mocked with deterministic vectors

## Backend Smoke Tests

### ST-V4-3.1: discover returns results from multiple sources
- **Validates:** Unified search across sources
- **Method:** Set up skills, templates, knowledge chunks; call discover
- **Checks:**
  - Returns results from at least 2 different source types
  - Each result has: type, name, description, score
  - Results sorted by score (highest first)

### ST-V4-3.2: discover with source filtering
- **Validates:** Source type filtering
- **Method:** Call discover with sources=["skills"]
- **Checks:**
  - Only skill results returned
  - No templates, knowledge, or memory results

### ST-V4-3.3: discover with no results
- **Validates:** Empty result handling
- **Method:** Call discover with query that matches nothing
- **Checks:**
  - Returns empty list, success=true, no error

### ST-V4-3.4: discover result format
- **Validates:** Unified format
- **Checks:**
  - Each result has type in: skill, template, mcp_server, knowledge, memory
  - Each result has name (non-empty string)
  - Each result has score (float 0-1)

### ST-V4-3.5: analyze_capabilities uses discover
- **Validates:** Internal integration
- **Method:** Call analyze_capabilities, check it returns unified results
- **Checks:**
  - Report includes results from discover
  - Still includes LLM assessment

### ST-V4-3.6: App integration — discover registered
- **Validates:** Wiring
- **Method:** Create app, check tools
- **Checks:**
  - `discover` appears in GET /tools
