# V4 Phase 1 — Smoke Tests

## Test Environment
- Prerequisites: V3P4 complete, all prior smoke tests passing
- LLM calls: always mocked

## Backend Smoke Tests

### ST-V4-1.1: LLMConfig default model is None
- **Validates:** No hardcoded minimax default
- **Checks:**
  - `LLMConfig()` has model=None
  - `LLMConfig(temperature=0.5)` has model=None

### ST-V4-1.2: OpenRouterProvider uses fallback model
- **Validates:** When config.model is None, provider uses its default
- **Checks:**
  - Provider constructed with default_model parameter
  - When called with LLMConfig(model=None), uses the default

### ST-V4-1.3: ToolType.INTERNAL exists, PROMPT_MACRO removed
- **Validates:** Enum cleanup
- **Checks:**
  - ToolType.INTERNAL == "internal"
  - ToolType.MCP == "mcp" (unchanged)
  - No ToolType.PROMPT_MACRO attribute

### ST-V4-1.4: Shared cosine_similarity in utils
- **Validates:** Utility extraction
- **Checks:**
  - `from agent_platform.core.utils import cosine_similarity` works
  - Returns correct values for known vectors

### ST-V4-1.5: Shared resolve_env_vars in utils
- **Validates:** Env var resolution utility
- **Checks:**
  - `resolve_env_vars({"KEY": "${VAR}"})` resolves from os.environ
  - Non-${} values pass through unchanged

### ST-V4-1.6: capability_tools uses agent model
- **Validates:** No minimax default in analyze/reflect
- **Method:** Create agent with specific model, call analyze_capabilities
- **Checks:**
  - LLM call uses agent's model, not minimax default

### ST-V4-1.7: All existing tests still pass
- **Validates:** No regressions from refactoring
- **Method:** Full smoke test suite
- **Checks:**
  - 171+ tests pass
