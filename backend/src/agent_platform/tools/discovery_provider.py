"""Unified capability discovery — search across all sources."""

import json
import logging
from typing import Any

from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)


class DiscoveryProvider:
    """Single discover() tool searching skills, templates,
    MCP servers, knowledge, and memories."""

    def __init__(
        self,
        skill_provider: Any | None = None,
        template_provider: Any | None = None,
        mcp_server_manager: Any | None = None,
        knowledge_store: Any | None = None,
        memory_store: Any | None = None,
        embedding_provider: Any | None = None,
    ) -> None:
        self._skills = skill_provider
        self._templates = template_provider
        self._mcp_mgr = mcp_server_manager
        self._knowledge = knowledge_store
        self._memory = memory_store
        self._embedder = embedding_provider

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="discover",
                description=(
                    "Search across all capability sources: "
                    "skills, templates, MCP servers, knowledge "
                    "base, and memories. Returns ranked results."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for",
                        },
                        "sources": {
                            "type": "string",
                            "description": (
                                "JSON list of sources to search: "
                                "skills, templates, mcp_servers, "
                                "knowledge, memories. "
                                "Default: all."
                            ),
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Max results (default 10)",
                        },
                    },
                    "required": ["query"],
                },
                tool_type=ToolType.INTERNAL,
                source="discovery",
            ),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        if name == "discover":
            return await self._discover(arguments)
        return ToolResult(
            success=False,
            error=f"Unknown: {name}",
        )

    async def _discover(
        self,
        args: dict[str, Any],
    ) -> ToolResult:
        query = args.get("query", "")
        top_k = args.get("top_k", 10)

        sources_raw = args.get("sources")
        if isinstance(sources_raw, str):
            try:
                sources = json.loads(sources_raw)
            except json.JSONDecodeError:
                sources = None
        else:
            sources = sources_raw

        all_results: list[dict[str, Any]] = []

        # Skills
        if self._skills and (sources is None or "skills" in sources):
            try:
                r = await self._skills.call_tool(
                    "list_skills",
                    {"query": query},
                )
                if r.success and r.output:
                    try:
                        items = json.loads(r.output)
                        if isinstance(items, list):
                            for i, item in enumerate(items):
                                all_results.append(
                                    {
                                        "type": "skill",
                                        "name": item.get("name", ""),
                                        "description": item.get("description", ""),
                                        "source": "skills",
                                        "score": max(0, 1.0 - i * 0.1),
                                    }
                                )
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception:
                logger.exception("Skill discovery failed")

        # Templates
        if self._templates and (sources is None or "templates" in sources):
            try:
                r = await self._templates.call_tool(
                    "list_templates",
                    {"query": query},
                )
                if r.success and r.output:
                    try:
                        items = json.loads(r.output)
                        if isinstance(items, list):
                            for i, item in enumerate(items):
                                all_results.append(
                                    {
                                        "type": "template",
                                        "name": item.get("name", ""),
                                        "description": item.get("description", ""),
                                        "source": "templates",
                                        "score": max(0, 1.0 - i * 0.1),
                                    }
                                )
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception:
                logger.exception("Template discovery failed")

        # MCP servers
        if self._mcp_mgr and (sources is None or "mcp_servers" in sources):
            try:
                r = await self._mcp_mgr.call_tool(
                    "list_mcp_servers",
                    {"query": query},
                )
                if r.success and r.output:
                    try:
                        items = json.loads(r.output)
                        if isinstance(items, list):
                            for i, item in enumerate(items):
                                all_results.append(
                                    {
                                        "type": "mcp_server",
                                        "name": item.get("name", ""),
                                        "description": item.get("description", ""),
                                        "source": "mcp_servers",
                                        "score": max(0, 1.0 - i * 0.1),
                                    }
                                )
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception:
                logger.exception("MCP server discovery failed")

        # Knowledge base
        if self._knowledge and (sources is None or "knowledge" in sources):
            try:
                chunks = self._knowledge.search(
                    query,
                    top_k=top_k,
                )
                for i, c in enumerate(chunks):
                    all_results.append(
                        {
                            "type": "knowledge",
                            "name": getattr(c, "source", ""),
                            "description": getattr(c, "content", str(c))[:200],
                            "source": getattr(c, "heading_path", ""),
                            "score": max(0, 1.0 - i * 0.1),
                        }
                    )
            except Exception:
                logger.exception("Knowledge discovery failed")

        # Memories
        if self._memory and (sources is None or "memories" in sources):
            try:
                results = await self._memory.search(
                    query,
                    top_k=top_k,
                )
                for i, m in enumerate(results):
                    all_results.append(
                        {
                            "type": "memory",
                            "name": getattr(m, "memory_type", "memory"),
                            "description": getattr(m, "content", str(m))[:200],
                            "source": "memories",
                            "score": max(0, 1.0 - i * 0.15),
                        }
                    )
            except Exception:
                logger.exception("Memory discovery failed")

        # Sort by score descending
        all_results.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        return ToolResult(
            success=True,
            output=json.dumps(
                all_results[:top_k],
                indent=2,
            ),
        )
