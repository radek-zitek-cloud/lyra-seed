"""Template discovery — lets agents find available agent templates.

Scans the prompts directory for paired {name}.json + {name}.md files
and exposes them via list_templates and get_template tools with
semantic search.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent_platform.core.utils import cosine_similarity
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)


class AgentTemplate(BaseModel):
    """A discovered agent template."""

    name: str
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    has_prompt: bool = False


def _extract_description(md_path: Path) -> str:
    """Extract description from first paragraph of prompt .md."""
    content = md_path.read_text(encoding="utf-8")
    # Skip header lines
    lines = content.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        # Skip headers, empty lines
        if stripped.startswith("#") or not stripped:
            continue
        # First non-header, non-empty line is the description
        return stripped[:200]
    return ""


class TemplateProvider:
    """ToolProvider for discovering agent templates."""

    def __init__(
        self,
        prompts_dir: str,
        embedding_provider: Any | None = None,
    ) -> None:
        self._prompts_dir = prompts_dir
        self._embedder = embedding_provider
        self._templates: dict[str, AgentTemplate] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Scan prompts directory for template pairs."""
        self._templates.clear()
        self._embeddings.clear()
        prompts_path = Path(self._prompts_dir)
        if not prompts_path.exists():
            return

        # Find all .json files (except default.json)
        for json_path in sorted(prompts_path.glob("*.json")):
            name = json_path.stem
            if name == "default":
                continue

            md_path = prompts_path / f"{name}.md"

            try:
                config = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                config = {}

            description = ""
            has_prompt = md_path.exists()
            if has_prompt:
                description = _extract_description(md_path)

            self._templates[name] = AgentTemplate(
                name=name,
                description=description,
                config=config,
                has_prompt=has_prompt,
            )

    async def _ensure_embeddings(self) -> None:
        if not self._embedder:
            return
        missing = [
            n
            for n in self._templates
            if n not in self._embeddings and self._templates[n].description
        ]
        if not missing:
            return
        descs = [self._templates[n].description for n in missing]
        try:
            vecs = await self._embedder.embed(descs)
            for name, vec in zip(missing, vecs):
                self._embeddings[name] = vec
        except Exception:
            logger.exception("Failed to embed templates")

    def reload(self) -> None:
        self._load_templates()

    def get_templates(self) -> dict[str, AgentTemplate]:
        return dict(self._templates)

    def get_template(self, name: str) -> AgentTemplate | None:
        return self._templates.get(name)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="list_templates",
                description=(
                    "List available agent templates for spawn_agent. "
                    "Supports semantic search via query parameter."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Semantic search query (e.g. 'code generation'). Omit to list all.",
                        },
                    },
                },
                tool_type=ToolType.INTERNAL,
                source="template",
            ),
            Tool(
                name="get_template",
                description=(
                    "Get full details of an agent template including "
                    "its system prompt, config overrides, and tool access."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Template name (e.g. 'coder', 'researcher').",
                        },
                    },
                    "required": ["name"],
                },
                tool_type=ToolType.INTERNAL,
                source="template",
            ),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        if name == "list_templates":
            return await self._list_templates(arguments)
        if name == "get_template":
            return self._get_template(arguments)
        return ToolResult(
            success=False,
            error=f"Unknown tool: {name}",
        )

    async def _list_templates(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        if not self._templates:
            return ToolResult(
                success=True,
                output="No agent templates found.",
            )

        query = arguments.get("query")
        templates = list(self._templates.values())

        if query and self._embedder:
            await self._ensure_embeddings()
            try:
                vecs = await self._embedder.embed([query])
                query_vec = vecs[0]
                scored = []
                for t in templates:
                    vec = self._embeddings.get(t.name)
                    if vec:
                        sim = cosine_similarity(query_vec, vec)
                        scored.append((sim, t))
                if scored:
                    scored.sort(
                        key=lambda x: x[0],
                        reverse=True,
                    )
                    templates = [t for _, t in scored]
            except Exception:
                logger.exception("Template search failed")

        info = [
            {
                "name": t.name,
                "description": t.description,
                "has_prompt": t.has_prompt,
                "config_keys": list(t.config.keys()),
            }
            for t in templates
        ]
        return ToolResult(
            success=True,
            output=json.dumps(info, indent=2),
        )

    def _get_template(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        name = arguments.get("name", "")
        tmpl = self._templates.get(name)
        if tmpl is None:
            return ToolResult(
                success=False,
                error=f"Template '{name}' not found.",
            )
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "name": tmpl.name,
                    "description": tmpl.description,
                    "config": tmpl.config,
                    "has_prompt": tmpl.has_prompt,
                },
                indent=2,
            ),
        )
