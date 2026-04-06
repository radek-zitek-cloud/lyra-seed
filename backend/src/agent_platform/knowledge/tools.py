"""Knowledge base tools — search and ingest documents."""

import json
import logging
from pathlib import Path
from typing import Any

from agent_platform.knowledge.store import KnowledgeStore
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)


class KnowledgeToolProvider:
    """ToolProvider for knowledge base operations."""

    def __init__(self, knowledge_store: KnowledgeStore) -> None:
        self._store = knowledge_store

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="search_knowledge",
                description=(
                    "Search the indexed knowledge base semantically. "
                    "Returns relevant document chunks with source attribution."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language search query.",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of results (default 5).",
                        },
                    },
                    "required": ["query"],
                },
                tool_type=ToolType.INTERNAL,
                source="knowledge",
            ),
            Tool(
                name="ingest_document",
                description=(
                    "Add a markdown document to the knowledge base. "
                    "Splits it into chunks by heading and indexes for semantic search."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the .md file to ingest.",
                        },
                    },
                    "required": ["path"],
                },
                tool_type=ToolType.INTERNAL,
                source="knowledge",
            ),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        if name == "search_knowledge":
            return self._search(arguments)
        if name == "ingest_document":
            return self._ingest(arguments)
        return ToolResult(
            success=False,
            error=f"Unknown: {name}",
        )

    def _search(self, args: dict[str, Any]) -> ToolResult:
        query = args.get("query", "")
        top_k = args.get("top_k", 5)

        if not query:
            return ToolResult(
                success=False,
                error="Query is required.",
            )

        chunks = self._store.search(query, top_k=top_k)

        results = [
            {
                "content": c.content[:500],
                "source": c.source,
                "heading_path": c.heading_path,
            }
            for c in chunks
        ]

        return ToolResult(
            success=True,
            output=json.dumps(results, indent=2),
        )

    def _ingest(self, args: dict[str, Any]) -> ToolResult:
        path_str = args.get("path", "")
        path = Path(path_str)

        if not path.exists():
            return ToolResult(
                success=False,
                error=f"File not found: {path_str}",
            )

        if not path.name.endswith(".md"):
            return ToolResult(
                success=False,
                error="Only .md files can be ingested.",
            )

        count = self._store.ingest(path)

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "path": path_str,
                    "chunks": count,
                    "source": path.name,
                }
            ),
        )
