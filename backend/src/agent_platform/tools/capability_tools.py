"""Capability tools — gap analysis, reflection, analytics, patterns.

Provides tools for self-improvement: analyzing what capabilities
are available, reflecting on completed work, querying tool usage
statistics, and storing/retrieving orchestration patterns.
"""

import json
import logging
from collections import defaultdict
from typing import Any

from agent_platform.llm.models import LLMConfig, Message, MessageRole
from agent_platform.memory.models import (
    DEFAULT_VISIBILITY,
    MemoryEntry,
    MemoryType,
)
from agent_platform.observation.events import EventFilter, EventType
from agent_platform.tools.models import Tool, ToolResult, ToolType

logger = logging.getLogger(__name__)

_REFLECT_DEFAULT = (
    "You are a post-task reflection engine.\n\n"
    "Task: {task}\n"
    "Outcome: {outcome}\n"
    "Tools used: {tools_used}\n\n"
    "Generate a concise retrospective covering:\n"
    "1. What approach was taken?\n"
    "2. What tools were most effective?\n"
    "3. What was missing or could be improved?\n"
    "4. What should be remembered for similar tasks?\n\n"
    "Be specific and actionable."
)


class CapabilityToolProvider:
    """Tools for capability analysis, reflection, and learning."""

    def __init__(
        self,
        llm_provider: Any,
        skill_provider: Any | None = None,
        template_provider: Any | None = None,
        mcp_server_manager: Any | None = None,
        memory_store: Any | None = None,
        event_bus: Any | None = None,
        embedding_provider: Any | None = None,
        reflect_prompt: str | None = None,
        agent_repo: Any | None = None,
    ) -> None:
        self._llm = llm_provider
        self._skills = skill_provider
        self._templates = template_provider
        self._mcp_mgr = mcp_server_manager
        self._memory = memory_store
        self._event_bus = event_bus
        self._embedder = embedding_provider
        self._reflect_prompt = reflect_prompt or _REFLECT_DEFAULT
        self._agent_repo = agent_repo

    async def _resolve_model(
        self,
        args: dict[str, Any],
    ) -> str | None:
        """Resolve model from agent config."""
        agent_id = args.get("agent_id")
        if agent_id and self._agent_repo:
            agent = await self._agent_repo.get(agent_id)
            if agent:
                return agent.config.model
        return None

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="analyze_capabilities",
                description=(
                    "Analyze what capabilities are available "
                    "for a task and identify gaps."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Task description",
                        },
                    },
                    "required": ["task"],
                },
                tool_type=ToolType.INTERNAL,
                source="capability",
            ),
            Tool(
                name="reflect",
                description=(
                    "Generate a post-task retrospective and store as PROCEDURE memory."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "outcome": {"type": "string"},
                        "tools_used": {"type": "string"},
                    },
                    "required": ["task", "outcome"],
                },
                tool_type=ToolType.INTERNAL,
                source="capability",
            ),
            Tool(
                name="tool_analytics",
                description=(
                    "Query tool usage statistics: "
                    "call count, success rate, avg duration."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Specific tool (optional)",
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "Top N tools (default 10)",
                        },
                    },
                },
                tool_type=ToolType.INTERNAL,
                source="capability",
            ),
            Tool(
                name="store_pattern",
                description=(
                    "Store a successful orchestration pattern for future reuse."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "strategy": {"type": "string"},
                        "subtasks": {
                            "type": "string",
                            "description": "JSON array of subtask descriptions",
                        },
                        "notes": {"type": "string"},
                    },
                    "required": ["task_type", "strategy"],
                },
                tool_type=ToolType.INTERNAL,
                source="capability",
            ),
            Tool(
                name="find_pattern",
                description=(
                    "Find reusable orchestration patterns matching a task description."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_description": {"type": "string"},
                        "top_k": {"type": "integer"},
                    },
                    "required": ["task_description"],
                },
                tool_type=ToolType.INTERNAL,
                source="capability",
            ),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        handlers = {
            "analyze_capabilities": self._analyze,
            "reflect": self._reflect,
            "tool_analytics": self._analytics,
            "store_pattern": self._store_pattern,
            "find_pattern": self._find_pattern,
        }
        handler = handlers.get(name)
        if not handler:
            return ToolResult(
                success=False,
                error=f"Unknown: {name}",
            )
        return await handler(arguments)

    # ── analyze_capabilities ──────────────────────────

    async def _analyze(
        self,
        args: dict[str, Any],
    ) -> ToolResult:
        task = args.get("task", "")
        available: dict[str, list] = {
            "skills": [],
            "templates": [],
            "mcp_servers": [],
            "relevant_memories": [],
        }

        # Search skills
        if self._skills:
            try:
                r = await self._skills.call_tool(
                    "list_skills",
                    {"query": task},
                )
                if r.success and r.output:
                    try:
                        available["skills"] = json.loads(r.output)
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception:
                logger.exception("Skill search failed")

        # Search templates
        if self._templates:
            try:
                r = await self._templates.call_tool(
                    "list_templates",
                    {"query": task},
                )
                if r.success and r.output:
                    try:
                        available["templates"] = json.loads(r.output)
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception:
                logger.exception("Template search failed")

        # Search MCP servers
        if self._mcp_mgr:
            try:
                r = await self._mcp_mgr.call_tool(
                    "list_mcp_servers",
                    {"query": task},
                )
                if r.success and r.output:
                    try:
                        available["mcp_servers"] = json.loads(r.output)
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception:
                logger.exception("MCP server search failed")

        # Search memories
        if self._memory:
            try:
                results = await self._memory.search(
                    task,
                    top_k=5,
                )
                available["relevant_memories"] = [
                    {"content": m.content, "type": m.memory_type}
                    if hasattr(m, "content")
                    else str(m)
                    for m in results
                ]
            except Exception:
                logger.exception("Memory search failed")

        # LLM assessment
        assessment = ""
        try:
            prompt = (
                f"Task: {task}\n\n"
                f"Available capabilities:\n"
                f"{json.dumps(available, indent=2, default=str)}\n\n"
                f"Analyze:\n"
                f"1. Which available capabilities are useful?\n"
                f"2. What capabilities are missing?\n"
                f"3. How should the gaps be filled?\n"
                f"Be concise and actionable."
            )
            config = LLMConfig(temperature=0.3)
            config.model = await self._resolve_model(args)
            resp = await self._llm.complete(
                [
                    Message(
                        role=MessageRole.HUMAN,
                        content=prompt,
                    )
                ],
                config=config,
            )
            assessment = resp.content or ""
        except Exception:
            logger.exception("Assessment LLM call failed")
            assessment = "Assessment unavailable."

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "task": task,
                    "available": available,
                    "assessment": assessment,
                }
            ),
        )

    # ── reflect ───────────────────────────────────────

    async def _reflect(
        self,
        args: dict[str, Any],
    ) -> ToolResult:
        task = args.get("task", "")
        outcome = args.get("outcome", "")
        tools_used = args.get("tools_used", "")

        # Generate reflection via LLM
        prompt = self._reflect_prompt.format(
            task=task,
            outcome=outcome,
            tools_used=tools_used,
        )

        try:
            config = LLMConfig(temperature=0.3)
            config.model = await self._resolve_model(args)
            resp = await self._llm.complete(
                [
                    Message(
                        role=MessageRole.HUMAN,
                        content=prompt,
                    )
                ],
                config=config,
            )
            reflection = resp.content or ""
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Reflection failed: {e}",
            )

        # Store as PROCEDURE memory
        if self._memory:
            structured_content = (
                f"[REFLECTION]\n"
                f"Task: {task}\n"
                f"Outcome: {outcome}\n"
                f"Tools: {tools_used}\n\n"
                f"Lessons learned:\n{reflection}"
            )
            entry = MemoryEntry(
                agent_id=args.get("agent_id", "system"),
                content=structured_content,
                memory_type=MemoryType.PROCEDURE,
                importance=0.7,
                visibility=DEFAULT_VISIBILITY[MemoryType.PROCEDURE],
            )
            try:
                await self._memory.add(entry)
            except Exception:
                logger.exception("Failed to store reflection")

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "reflection": reflection,
                    "stored": self._memory is not None,
                }
            ),
        )

    # ── tool_analytics ────────────────────────────────

    async def _analytics(
        self,
        args: dict[str, Any],
    ) -> ToolResult:
        if not self._event_bus:
            return ToolResult(
                success=True,
                output="No event bus available for analytics.",
            )

        tool_name = args.get("tool_name")
        top_n = args.get("top_n", 10)

        try:
            events = await self._event_bus.query(
                EventFilter(
                    event_types=[EventType.TOOL_RESULT],
                ),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Event query failed: {e}",
            )

        # Aggregate stats
        stats: dict[str, dict] = defaultdict(
            lambda: {
                "call_count": 0,
                "success_count": 0,
                "total_duration_ms": 0,
            },
        )

        for e in events:
            name = e.payload.get("tool_name", "")
            if not name:
                continue
            if tool_name and name != tool_name:
                continue
            s = stats[name]
            s["call_count"] += 1
            if e.payload.get("success", True):
                s["success_count"] += 1
            if e.duration_ms:
                s["total_duration_ms"] += e.duration_ms

        result = []
        for tname, s in sorted(
            stats.items(),
            key=lambda x: x[1]["call_count"],
            reverse=True,
        )[:top_n]:
            count = s["call_count"]
            result.append(
                {
                    "tool_name": tname,
                    "call_count": count,
                    "success_rate": (s["success_count"] / count if count > 0 else 0),
                    "avg_duration_ms": (
                        s["total_duration_ms"] / count if count > 0 else 0
                    ),
                }
            )

        return ToolResult(
            success=True,
            output=json.dumps(result, indent=2),
        )

    # ── store_pattern ─────────────────────────────────

    async def _store_pattern(
        self,
        args: dict[str, Any],
    ) -> ToolResult:
        task_type = args.get("task_type", "")
        strategy = args.get("strategy", "")
        subtasks_raw = args.get("subtasks", "[]")
        notes = args.get("notes", "")

        if isinstance(subtasks_raw, str):
            try:
                subtasks = json.loads(subtasks_raw)
            except json.JSONDecodeError:
                subtasks = [subtasks_raw]
        else:
            subtasks = subtasks_raw

        content = (
            f"[PATTERN]\nTask type: {task_type}\nStrategy: {strategy}\nSubtasks:\n"
        )
        for i, st in enumerate(subtasks, 1):
            content += f"  {i}. {st}\n"
        if notes:
            content += f"Notes: {notes}\n"

        if not self._memory:
            return ToolResult(
                success=True,
                output=json.dumps(
                    {
                        "stored": False,
                        "reason": "No memory store available",
                    }
                ),
            )

        entry = MemoryEntry(
            agent_id=args.get("agent_id", "system"),
            content=content,
            memory_type=MemoryType.PROCEDURE,
            importance=0.8,
            visibility=DEFAULT_VISIBILITY[MemoryType.PROCEDURE],
        )

        try:
            await self._memory.add(entry)
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to store pattern: {e}",
            )

        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "stored": True,
                    "task_type": task_type,
                    "strategy": strategy,
                }
            ),
        )

    # ── find_pattern ──────────────────────────────────

    async def _find_pattern(
        self,
        args: dict[str, Any],
    ) -> ToolResult:
        query = args.get("task_description", "")
        top_k = args.get("top_k", 5)

        if not self._memory:
            return ToolResult(
                success=True,
                output=json.dumps([]),
            )

        try:
            results = await self._memory.search(
                query,
                top_k=top_k,
                memory_type=MemoryType.PROCEDURE,
            )
        except Exception:
            # Some stores don't support memory_type filter
            try:
                results = await self._memory.search(
                    query,
                    top_k=top_k,
                )
                results = [
                    r
                    for r in results
                    if hasattr(r, "memory_type")
                    and r.memory_type == MemoryType.PROCEDURE
                ]
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=f"Pattern search failed: {e}",
                )

        patterns = [
            {
                "id": getattr(r, "id", ""),
                "content": getattr(r, "content", str(r)),
                "importance": getattr(r, "importance", 0),
            }
            for r in results
        ]

        return ToolResult(
            success=True,
            output=json.dumps(patterns, indent=2),
        )
