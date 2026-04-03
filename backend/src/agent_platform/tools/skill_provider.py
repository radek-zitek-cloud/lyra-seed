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
import math
import os
import re
import time
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agent_platform.llm.models import (
    LLMConfig,
    Message,
    MessageRole,
)
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_VERSION_RE = re.compile(r"\.v\d+$")

RESERVED_NAMES = frozenset(
    {
        "list_skills",
        "create_skill",
        "test_skill",
        "update_skill",
        "remember",
        "recall",
        "forget",
        "spawn_agent",
        "wait_for_agent",
        "get_agent_result",
        "list_child_agents",
        "send_message",
        "receive_messages",
        "check_agent_status",
        "stop_agent",
        "dismiss_agent",
        "decompose_task",
        "orchestrate",
    }
)

_EVAL_PROMPT_DEFAULT = (
    "Evaluate whether the following output fulfills "
    "the skill's stated purpose.\n\n"
    "Skill purpose: {description}\n\n"
    "Skill output:\n{output}\n\n"
    "Respond with ONLY valid JSON:\n"
    '{{"verdict": "PASS or FAIL", '
    '"reasoning": "brief explanation"}}'
)


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
        return Skill(name=path.stem, template=content.strip())

    parts = content.split("---", 2)
    if len(parts) < 3:
        return Skill(name=path.stem, template=content.strip())

    frontmatter_str = parts[1].strip()
    template = parts[2].strip()
    fm = yaml.safe_load(frontmatter_str) or {}

    return Skill(
        name=fm.get("name", path.stem),
        description=fm.get("description", ""),
        parameters=fm.get("parameters", {}),
        template=template,
    )


def _params_to_json_schema(params: dict[str, Any]) -> dict[str, Any]:
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
            if pdef.get("required") in (True, "true", "True"):
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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _build_skill_file(
    name: str,
    description: str,
    params: dict,
    template: str,
) -> str:
    """Build skill .md file content."""
    lines = ["---", f"name: {name}"]
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
    return "\n".join(lines)


class SkillProvider:
    """ToolProvider that loads skills from .md files."""

    def __init__(
        self,
        skills_dir: str,
        llm_provider: Any,
        agent_repo: Any | None = None,
        embedding_provider: Any | None = None,
        dedup_threshold: float = 0.85,
        eval_prompt: str | None = None,
    ) -> None:
        self._skills_dir = skills_dir
        self._llm = llm_provider
        self._agent_repo = agent_repo
        self._embedder = embedding_provider
        self._dedup_threshold = dedup_threshold
        self._eval_prompt = eval_prompt or _EVAL_PROMPT_DEFAULT
        self._skills: dict[str, Skill] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._load_skills()

    def get_skills(self) -> dict[str, Skill]:
        """Return all loaded skills."""
        return dict(self._skills)

    def get_skill(self, name: str) -> Skill | None:
        """Return a specific skill by name."""
        return self._skills.get(name)

    def _load_skills(self) -> None:
        """Scan skills directory and load all .md files."""
        self._skills.clear()
        self._embeddings.clear()
        skills_path = Path(self._skills_dir)
        if not skills_path.exists():
            return

        for path in sorted(skills_path.glob("*.md")):
            if path.name.startswith("README"):
                continue
            # Skip version files (e.g., foo.v1.md)
            stem = path.stem
            if _VERSION_RE.search(stem):
                continue
            try:
                skill = parse_skill_file(path)
                self._skills[skill.name] = skill
            except Exception:
                logger.exception("Failed to parse: %s", path)

    async def _ensure_embeddings(self) -> None:
        """Compute embeddings for skills that don't have them."""
        if not self._embedder:
            return
        missing = [
            name
            for name in self._skills
            if name not in self._embeddings and self._skills[name].description
        ]
        if not missing:
            return
        descs = [self._skills[n].description for n in missing]
        try:
            vecs = await self._embedder.embed(descs)
            for name, vec in zip(missing, vecs):
                self._embeddings[name] = vec
        except Exception:
            logger.exception("Failed to compute skill embeddings")

    def reload(self) -> None:
        """Re-scan the skills directory."""
        self._load_skills()

    # ── Tool registration ─────────────────────────────

    async def list_tools(self) -> list[Tool]:
        """Return skills + management tools."""
        tools = [
            Tool(
                name=s.name,
                description=s.description,
                input_schema=_params_to_json_schema(s.parameters),
                tool_type=ToolType.PROMPT_MACRO,
                source="skill",
            )
            for s in self._skills.values()
        ]
        for name, desc, schema in [
            (
                "list_skills",
                "List available skills. Use query for semantic search.",
                {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (optional)",
                        },
                    },
                },
            ),
            (
                "create_skill",
                "Create a new reusable skill.",
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "template": {
                            "type": "string",
                            "description": "Prompt with {{param}}",
                        },
                        "parameters": {
                            "type": "string",
                            "description": "JSON params definition",
                        },
                    },
                    "required": ["name", "template"],
                },
            ),
            (
                "test_skill",
                "Dry-run a skill template and evaluate the output.",
                {
                    "type": "object",
                    "properties": {
                        "template": {"type": "string"},
                        "description": {
                            "type": "string",
                            "description": "Expected purpose",
                        },
                        "test_args": {
                            "type": "string",
                            "description": "JSON test arguments",
                        },
                    },
                    "required": ["template", "description"],
                },
            ),
            (
                "update_skill",
                "Update an existing skill (versions the old one).",
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "template": {"type": "string"},
                        "parameters": {"type": "string"},
                    },
                    "required": ["name", "template"],
                },
            ),
        ]:
            tools.append(
                Tool(
                    name=name,
                    description=desc,
                    input_schema=schema,
                    tool_type=ToolType.PROMPT_MACRO,
                    source="skill",
                )
            )
        return tools

    # ── Tool dispatch ─────────────────────────────────

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        if name == "list_skills":
            return await self._list_skills(arguments)
        if name == "create_skill":
            return await self._create_skill(arguments)
        if name == "test_skill":
            return await self._test_skill(arguments)
        if name == "update_skill":
            return await self._update_skill(arguments)
        return await self._execute_skill(name, arguments)

    # ── list_skills ───────────────────────────────────

    async def _list_skills(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        if not self._skills:
            return ToolResult(
                success=True,
                output="No skills are currently loaded.",
            )

        query = arguments.get("query")
        skills_list = list(self._skills.values())

        # Semantic search if query provided and embedder available
        if query and self._embedder:
            await self._ensure_embeddings()
            try:
                vecs = await self._embedder.embed([query])
                query_vec = vecs[0]
                scored = []
                for s in skills_list:
                    vec = self._embeddings.get(s.name)
                    if vec:
                        sim = _cosine_similarity(query_vec, vec)
                        scored.append((sim, s))
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    skills_list = [s for _, s in scored]
            except Exception:
                logger.exception("Skill search failed")

        info = [
            {
                "name": s.name,
                "description": s.description,
                "parameters": list(s.parameters.keys()),
            }
            for s in skills_list
        ]
        return ToolResult(
            success=True,
            output=json.dumps(info, indent=2),
        )

    # ── execute_skill ─────────────────────────────────

    async def _execute_skill(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        skill = self._skills.get(name)
        if skill is None:
            return ToolResult(success=False, error=f"Unknown skill: {name}")

        expanded = skill.template
        for key, value in arguments.items():
            if key == "agent_id":
                continue
            expanded = expanded.replace(f"{{{{{key}}}}}", str(value))

        config = LLMConfig(temperature=0.5)
        agent_id = arguments.get("agent_id")
        if agent_id and self._agent_repo:
            agent = await self._agent_repo.get(agent_id)
            if agent:
                config.model = agent.config.model

        start = time.monotonic()
        try:
            resp = await self._llm.complete(
                [Message(role=MessageRole.HUMAN, content=expanded)],
                config=config,
            )
            return ToolResult(
                success=True,
                output=resp.content or "",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    # ── test_skill ────────────────────────────────────

    async def _test_skill(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        template = arguments.get("template", "")
        description = arguments.get("description", "")
        test_args_raw = arguments.get("test_args", "{}")

        if isinstance(test_args_raw, str):
            try:
                test_args = json.loads(test_args_raw)
            except json.JSONDecodeError:
                test_args = {}
        else:
            test_args = test_args_raw

        # Expand template
        expanded = template
        for key, value in test_args.items():
            expanded = expanded.replace(f"{{{{{key}}}}}", str(value))

        # Resolve agent model
        config = LLMConfig(temperature=0.5)
        agent_id = arguments.get("agent_id")
        if agent_id and self._agent_repo:
            agent = await self._agent_repo.get(agent_id)
            if agent:
                config.model = agent.config.model

        start = time.monotonic()
        try:
            # Call 1: Execute the template
            exec_resp = await self._llm.complete(
                [Message(role=MessageRole.HUMAN, content=expanded)],
                config=config,
            )
            output = exec_resp.content or ""

            # Call 2: Evaluate the output
            eval_prompt = self._eval_prompt.format(
                description=description,
                output=output,
            )
            eval_config = LLMConfig(temperature=0.1)
            if agent_id and self._agent_repo:
                agent = await self._agent_repo.get(agent_id)
                if agent:
                    orch_model = agent.config.orchestration_model or agent.config.model
                    eval_config.model = orch_model

            eval_resp = await self._llm.complete(
                [Message(role=MessageRole.HUMAN, content=eval_prompt)],
                config=eval_config,
            )
            eval_raw = eval_resp.content or ""

            # Parse evaluation
            verdict = "UNKNOWN"
            reasoning = eval_raw
            try:
                # Strip markdown fences
                cleaned = eval_raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    cleaned = "\n".join(lines[1:])
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                eval_data = json.loads(cleaned)
                verdict = eval_data.get("verdict", "UNKNOWN")
                reasoning = eval_data.get("reasoning", eval_raw)
            except json.JSONDecodeError:
                if "PASS" in eval_raw.upper():
                    verdict = "PASS"
                elif "FAIL" in eval_raw.upper():
                    verdict = "FAIL"

            return ToolResult(
                success=True,
                output=json.dumps(
                    {
                        "output": output,
                        "verdict": verdict,
                        "reasoning": reasoning,
                    }
                ),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    # ── create_skill ──────────────────────────────────

    async def _create_skill(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        name = arguments.get("name", "")
        if not name:
            return ToolResult(
                success=False,
                error="Skill name is required",
            )

        # Validate name format
        if not _NAME_RE.match(name):
            return ToolResult(
                success=False,
                error=(
                    f"Invalid skill name '{name}'. "
                    "Use only letters, numbers, hyphens, "
                    "and underscores."
                ),
            )

        # Check reserved names
        if name in RESERVED_NAMES:
            return ToolResult(
                success=False,
                error=f"'{name}' is a reserved tool name.",
            )

        # Check existing
        if name in self._skills:
            return ToolResult(
                success=False,
                error=f"Skill '{name}' already exists",
            )

        description = arguments.get("description", "")
        template = arguments.get("template", "")
        params_raw = arguments.get("parameters", "{}")
        if isinstance(params_raw, str):
            try:
                params = json.loads(params_raw)
            except json.JSONDecodeError:
                params = {}
        else:
            params = params_raw

        # Semantic deduplication
        if description and self._embedder:
            await self._ensure_embeddings()
            try:
                new_vec = (await self._embedder.embed([description]))[0]
                for sname, vec in self._embeddings.items():
                    sim = _cosine_similarity(new_vec, vec)
                    if sim >= self._dedup_threshold:
                        return ToolResult(
                            success=False,
                            error=(
                                f"Too similar to existing skill "
                                f"'{sname}' "
                                f"(similarity: {sim:.2f}). "
                                f"Use update_skill to modify it, "
                                f"or change the description."
                            ),
                        )
            except Exception:
                logger.exception("Dedup check failed")

        # Write file
        content = _build_skill_file(name, description, params, template)
        skills_path = Path(self._skills_dir)
        os.makedirs(skills_path, exist_ok=True)
        file_path = skills_path / f"{name}.md"

        try:
            file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write: {e}",
            )

        self.reload()
        # Recompute embedding for the new skill
        if description and self._embedder:
            try:
                vecs = await self._embedder.embed([description])
                self._embeddings[name] = vecs[0]
            except Exception:
                pass

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

    # ── update_skill ──────────────────────────────────

    async def _update_skill(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        name = arguments.get("name", "")
        if name not in self._skills:
            return ToolResult(
                success=False,
                error=(
                    f"Skill '{name}' does not exist. "
                    f"Use create_skill to create a new skill."
                ),
            )

        template = arguments.get("template", "")
        if not template:
            return ToolResult(
                success=False,
                error="Template is required",
            )

        description = arguments.get("description", "")
        params_raw = arguments.get("parameters", "{}")
        if isinstance(params_raw, str):
            try:
                params = json.loads(params_raw)
            except json.JSONDecodeError:
                params = {}
        else:
            params = params_raw

        skills_path = Path(self._skills_dir)
        current_file = skills_path / f"{name}.md"

        # Find next version number
        n = 1
        while (skills_path / f"{name}.v{n}.md").exists():
            n += 1

        # Rename current to version
        version_file = skills_path / f"{name}.v{n}.md"
        if current_file.exists():
            current_file.rename(version_file)

        # Write new version
        if not description:
            description = self._skills[name].description
        content = _build_skill_file(name, description, params, template)
        current_file.write_text(content, encoding="utf-8")

        self.reload()
        # Update embedding
        if description and self._embedder:
            try:
                vecs = await self._embedder.embed([description])
                self._embeddings[name] = vecs[0]
            except Exception:
                pass

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "name": name,
                    "version": n,
                    "version_file": str(version_file),
                    "status": "updated",
                }
            ),
        )
