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


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class PlatformConfig(BaseModel):
    """Platform-level configuration loaded from lyra.config.json."""

    defaultModel: str = "openai/gpt-4.1-mini"
    mcpServers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    systemPromptsDir: str = "./prompts"


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
