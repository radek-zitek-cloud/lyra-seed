"""Skill provider — filesystem-based prompt templates.

Skills are .md files with YAML frontmatter:

---
name: summarize
description: Summarize text into bullet points
parameters:
  text:
    type: string
    description: The text to summarize
    required: true
---

Summarize into 3-5 bullet points:

{{text}}
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agent_platform.llm.models import (
    LLMConfig,
    LLMResponse,
    Message,
    MessageRole,
)
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)


class Skill(BaseModel):
    """A parsed skill definition."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    template: str = ""


def parse_skill_file(path: Path) -> Skill:
    """Parse a skill .md file into a Skill object."""
    content = path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return Skill(
            name=path.stem,
            template=content.strip(),
        )

    parts = content.split("---", 2)
    if len(parts) < 3:
        return Skill(
            name=path.stem,
            template=content.strip(),
        )

    frontmatter_str = parts[1].strip()
    template = parts[2].strip()

    fm = yaml.safe_load(frontmatter_str) or {}

    return Skill(
        name=fm.get("name", path.stem),
        description=fm.get("description", ""),
        parameters=fm.get("parameters", {}),
        template=template,
    )


def _params_to_json_schema(
    params: dict[str, Any],
) -> dict[str, Any]:
    """Convert skill parameters to JSON Schema."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, pdef in params.items():
        if isinstance(pdef, dict):
            prop: dict[str, Any] = {
                "type": pdef.get("type", "string"),
            }
            if "description" in pdef:
                prop["description"] = pdef["description"]
            properties[pname] = prop
            if pdef.get("required") in (
                True,
                "true",
                "True",
            ):
                required.append(pname)
        else:
            properties[pname] = {"type": "string"}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


class SkillProvider:
    """ToolProvider that loads skills from .md files."""

    def __init__(
        self,
        skills_dir: str,
        llm_provider: Any,
        agent_repo: Any | None = None,
    ) -> None:
        self._skills_dir = skills_dir
        self._llm = llm_provider
        self._agent_repo = agent_repo
        self._skills: dict[str, Skill] = {}
        self._load_skills()

    def get_skills(self) -> dict[str, Skill]:
        """Return all loaded skills (public accessor)."""
        return dict(self._skills)

    def get_skill(self, name: str) -> Skill | None:
        """Return a specific skill by name, or None."""
        return self._skills.get(name)

    def _load_skills(self) -> None:
        """Scan skills directory and load all .md files."""
        self._skills.clear()
        skills_path = Path(self._skills_dir)
        if not skills_path.exists():
            logger.info(
                "Skills directory does not exist: %s",
                self._skills_dir,
            )
            return

        for path in sorted(skills_path.glob("*.md")):
            if path.name.startswith("README"):
                continue
            try:
                skill = parse_skill_file(path)
                self._skills[skill.name] = skill
                logger.info("Loaded skill: %s", skill.name)
            except Exception:
                logger.exception(
                    "Failed to parse skill: %s",
                    path,
                )

    def reload(self) -> None:
        """Re-scan the skills directory."""
        self._load_skills()

    async def list_tools(self) -> list[Tool]:
        """Return skills + create_skill as tools."""
        tools = [
            Tool(
                name=skill.name,
                description=skill.description,
                input_schema=_params_to_json_schema(
                    skill.parameters,
                ),
                tool_type=ToolType.PROMPT_MACRO,
                source="skill",
            )
            for skill in self._skills.values()
        ]
        # Always include create_skill
        tools.append(
            Tool(
                name="create_skill",
                description=(
                    "Create a new reusable skill. "
                    "The skill becomes immediately "
                    "available as a tool."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Skill name",
                        },
                        "description": {
                            "type": "string",
                            "description": ("What the skill does"),
                        },
                        "template": {
                            "type": "string",
                            "description": (
                                "Prompt template with {{param}} placeholders"
                            ),
                        },
                        "parameters": {
                            "type": "string",
                            "description": ("JSON object defining parameters"),
                        },
                    },
                    "required": ["name", "template"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="skill",
            ),
        )
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a skill or create a new one."""
        if name == "create_skill":
            return await self._create_skill(arguments)
        return await self._execute_skill(
            name,
            arguments,
        )

    async def _execute_skill(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Expand template and run LLM sub-call."""
        skill = self._skills.get(name)
        if skill is None:
            return ToolResult(
                success=False,
                error=f"Unknown skill: {name}",
            )

        # Expand template
        expanded = skill.template
        for key, value in arguments.items():
            if key == "agent_id":
                continue
            expanded = expanded.replace(
                f"{{{{{key}}}}}",
                str(value),
            )

        messages = [
            Message(
                role=MessageRole.HUMAN,
                content=expanded,
            ),
        ]

        # Resolve model from agent config
        config = LLMConfig(temperature=0.5)
        agent_id = arguments.get("agent_id")
        if agent_id and self._agent_repo:
            agent = await self._agent_repo.get(agent_id)
            if agent:
                config.model = agent.config.model

        start = time.monotonic()
        try:
            response: LLMResponse = await self._llm.complete(
                messages,
                config=config,
            )
            return ToolResult(
                success=True,
                output=response.content or "",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def _create_skill(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Write a new skill file to disk."""
        name = arguments.get("name", "")
        if not name:
            return ToolResult(
                success=False,
                error="Skill name is required",
            )

        # Check for conflicts
        if name in self._skills or name == "create_skill":
            return ToolResult(
                success=False,
                error=f"Skill '{name}' already exists",
            )

        description = arguments.get("description", "")
        template = arguments.get("template", "")
        params_raw = arguments.get("parameters", "{}")

        # Parse parameters
        if isinstance(params_raw, str):
            try:
                params = json.loads(params_raw)
            except json.JSONDecodeError:
                params = {}
        else:
            params = params_raw

        # Build file content
        lines = ["---"]
        lines.append(f"name: {name}")
        if description:
            lines.append(f"description: {description}")
        if params:
            lines.append("parameters:")
            for pname, pdef in params.items():
                lines.append(f"  {pname}:")
                if isinstance(pdef, dict):
                    for k, v in pdef.items():
                        lines.append(f"    {k}: {v}")
                else:
                    lines.append("    type: string")
        lines.append("---")
        lines.append("")
        lines.append(template)

        # Write file
        skills_path = Path(self._skills_dir)
        os.makedirs(skills_path, exist_ok=True)
        file_path = skills_path / f"{name}.md"

        try:
            file_path.write_text(
                "\n".join(lines),
                encoding="utf-8",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write skill: {e}",
            )

        # Reload to make it available
        self.reload()

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "name": name,
                    "file": str(file_path),
                    "status": "created",
                }
            ),
        )
