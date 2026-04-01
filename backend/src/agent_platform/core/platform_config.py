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
    base = Path(prompts_dir)
    if not base.is_absolute():
        base = project_root / base

    # Sanitize agent name for filesystem
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "-" for c in agent_name.lower()
    )

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
