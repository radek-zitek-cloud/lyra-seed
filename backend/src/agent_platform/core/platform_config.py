"""Platform configuration loaded from lyra.config.json.

Config file format (Claude Code style):
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": { "KEY": "value" }
    }
  },
  "systemPromptsDir": "./prompts"
}
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


class RetryConfig(BaseModel):
    """Retry configuration for LLM API calls."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    timeout: float = 60.0


class HITLConfig(BaseModel):
    """HITL gate configuration."""

    timeout_seconds: float = 300


class MemoryGCConfig(BaseModel):
    """Memory garbage collection configuration."""

    prune_threshold: float = 0.1
    max_entries: int = 500
    dedup_threshold: float = 0.9
    half_life_days: float = 7.0
    decay_weights: list[float] = Field(
        default_factory=lambda: [0.6, 0.2, 0.2],
        description="Weights for [base_decay, access_boost, importance_boost]",
    )


class ContextConfig(BaseModel):
    """Context compression configuration."""

    max_tokens: int = 100_000
    memory_top_k: int = 5


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class PlatformConfig(BaseModel):
    """Platform-level configuration loaded from lyra.config.json."""

    dataDir: str = "./data"
    defaultModel: str = "openai/gpt-4.1-mini"
    embeddingModel: str = "openai/text-embedding-3-large"
    mcpServers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    systemPromptsDir: str = "./prompts"
    modelCosts: dict[str, list[float]] = Field(default_factory=dict)
    defaultModelCost: list[float] = Field(default_factory=lambda: [1.0, 4.0])
    retry: RetryConfig = Field(default_factory=RetryConfig)
    hitl: HITLConfig = Field(default_factory=HITLConfig)
    memoryGC: MemoryGCConfig = Field(default_factory=MemoryGCConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    summaryModel: str = "openai/gpt-4.1-nano"
    extractionModel: str = "openai/gpt-4.1-nano"
    orchestrationModel: str | None = None
    maxSubtasks: int = 10
    orchestrationTemperature: float = 0.3
    mcpRequestTimeout: float = 30.0
    maxSpawnDepth: int = 3
    skillsDir: str = "./skills"
    mcpServersDir: str = "./mcp-servers"


def load_platform_config(project_root: Path) -> PlatformConfig:
    """Load platform config from lyra.config.json at project root."""
    config_path = project_root / "lyra.config.json"
    if not config_path.exists():
        logger.info("No lyra.config.json found at %s, using defaults", project_root)
        return PlatformConfig()

    with open(config_path) as f:
        data: dict[str, Any] = json.load(f)

    config = PlatformConfig.model_validate(data)
    logger.info(
        "Loaded config: %d MCP servers, prompts dir: %s",
        len(config.mcpServers),
        config.systemPromptsDir,
    )
    return config


def load_system_prompt(name: str, project_root: Path) -> str | None:
    """Load a system prompt from prompts/system/{name}.md.

    Returns None if the file doesn't exist.
    """
    prompt_path = project_root / "prompts" / "system" / f"{name}.md"
    if prompt_path.exists():
        logger.info("Loaded system prompt: %s", prompt_path)
        return prompt_path.read_text(encoding="utf-8").strip()
    return None


class AgentFileConfig(BaseModel):
    """Agent configuration loaded from {name}.json in prompts dir.

    Example {prompts_dir}/my-agent.json:
    {
      "model": "anthropic/claude-sonnet-4",
      "hitl_policy": "always_ask",
      "temperature": 0.5,
      "max_iterations": 20
    }
    """

    model: str | None = None
    hitl_policy: str | None = None
    temperature: float | None = None
    max_iterations: int | None = None
    retry: RetryConfig | None = None
    hitl: HITLConfig | None = None
    memoryGC: MemoryGCConfig | None = None
    context: ContextConfig | None = None
    summary_model: str | None = None
    extraction_model: str | None = None
    orchestration_model: str | None = None
    max_subtasks: int | None = None
    auto_extract: bool | None = None
    memory_sharing: dict[str, str] | None = None
    allowed_mcp_servers: list[str] | None = None
    allowed_tools: list[str] | None = None


def _sanitize_name(agent_name: str) -> str:
    """Sanitize agent name for filesystem lookup."""
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in agent_name.lower())


def _resolve_prompts_dir(prompts_dir: str, project_root: Path) -> Path:
    base = Path(prompts_dir)
    if not base.is_absolute():
        base = project_root / base
    return base


def resolve_system_prompt(
    agent_name: str,
    prompts_dir: str,
    project_root: Path,
) -> str:
    """Resolve system prompt for an agent by name.

    Resolution order:
    1. {prompts_dir}/{agent_name}.md
    2. {prompts_dir}/default.md
    3. Hardcoded fallback
    """
    base = _resolve_prompts_dir(prompts_dir, project_root)
    safe_name = _sanitize_name(agent_name)

    # Try name-specific prompt
    name_path = base / f"{safe_name}.md"
    if name_path.exists():
        logger.info("Loading system prompt from %s", name_path)
        return name_path.read_text(encoding="utf-8").strip()

    # Try default prompt
    default_path = base / "default.md"
    if default_path.exists():
        logger.info("Loading default system prompt from %s", default_path)
        return default_path.read_text(encoding="utf-8").strip()

    # Hardcoded fallback
    logger.info("No prompt files found, using hardcoded fallback")
    return DEFAULT_SYSTEM_PROMPT


def resolve_agent_config(
    agent_name: str,
    prompts_dir: str,
    project_root: Path,
) -> AgentFileConfig:
    """Load agent config overrides from {name}.json.

    Resolution order:
    1. {prompts_dir}/{agent_name}.json
    2. {prompts_dir}/default.json
    3. Empty config (no overrides)
    """
    base = _resolve_prompts_dir(prompts_dir, project_root)
    safe_name = _sanitize_name(agent_name)

    # Try name-specific config
    name_path = base / f"{safe_name}.json"
    if name_path.exists():
        logger.info("Loading agent config from %s", name_path)
        with open(name_path) as f:
            data = json.load(f)
        return AgentFileConfig.model_validate(data)

    # Try default config
    default_path = base / "default.json"
    if default_path.exists():
        logger.info("Loading default agent config from %s", default_path)
        with open(default_path) as f:
            data = json.load(f)
        return AgentFileConfig.model_validate(data)

    return AgentFileConfig()
