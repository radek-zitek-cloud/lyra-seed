"""Agent spawner — tools for creating and managing sub-agents."""

import json
import time
from collections.abc import Callable
from typing import Any

from agent_platform.core.models import (
    Agent,
    AgentConfig,
    AgentResponse,
    AgentStatus,
    Conversation,
)
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.llm.models import LLMConfig, LLMResponse, Message, MessageRole
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.models import Tool, ToolResult, ToolType


class AgentSpawnerProvider:
    """ToolProvider that lets agents spawn and manage sub-agents."""

    def __init__(
        self,
        agent_repo: SqliteAgentRepo,
        conversation_repo: SqliteConversationRepo,
        llm_provider: object,
        event_bus: InProcessEventBus,
        context_manager: object | None = None,
        extractor: object | None = None,
        system_prompt_resolver: Callable[[str], str] | None = None,
        agent_config_resolver: Callable | None = None,
    ) -> None:
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._llm = llm_provider
        self._event_bus = event_bus
        self._context_manager = context_manager
        self._extractor = extractor
        self._resolve_prompt = system_prompt_resolver
        self._resolve_config = agent_config_resolver

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="spawn_agent",
                description=(
                    "Create and run a sub-agent to handle a specific task. "
                    "The sub-agent runs to completion and returns its response."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the sub-agent",
                        },
                        "task": {
                            "type": "string",
                            "description": "The task/prompt to give the sub-agent",
                        },
                        "template": {
                            "type": "string",
                            "description": (
                                "Template name to load prompt and config "
                                "from prompts/{template}.md and "
                                "prompts/{template}.json (optional)"
                            ),
                        },
                        "system_prompt": {
                            "type": "string",
                            "description": (
                                "Custom system prompt — overrides template "
                                "prompt if both provided (optional)"
                            ),
                        },
                        "model": {
                            "type": "string",
                            "description": "LLM model override (optional)",
                        },
                        "temperature": {
                            "type": "number",
                            "description": "Temperature override (optional)",
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Parent agent ID (auto-injected)",
                        },
                    },
                    "required": ["name", "task"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="agent_spawner",
            ),
            Tool(
                name="wait_for_agent",
                description="Wait for a child agent to complete and return its result.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {
                            "type": "string",
                            "description": "ID of the child agent to wait for",
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Parent agent ID (auto-injected)",
                        },
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="agent_spawner",
            ),
            Tool(
                name="get_agent_result",
                description=(
                    "Get the current status and last response of a child agent. "
                    "Non-blocking — returns immediately."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "child_agent_id": {
                            "type": "string",
                            "description": "ID of the child agent",
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Parent agent ID (auto-injected)",
                        },
                    },
                    "required": ["child_agent_id"],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="agent_spawner",
            ),
            Tool(
                name="list_child_agents",
                description="List all child agents spawned by this agent.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Parent agent ID (auto-injected)",
                        },
                    },
                    "required": [],
                },
                tool_type=ToolType.PROMPT_MACRO,
                source="agent_spawner",
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        start = time.monotonic()
        if name == "spawn_agent":
            return await self._spawn_agent(arguments, start)
        elif name == "wait_for_agent":
            return await self._wait_for_agent(arguments, start)
        elif name == "get_agent_result":
            return await self._get_agent_result(arguments, start)
        elif name == "list_child_agents":
            return await self._list_child_agents(arguments, start)
        return ToolResult(success=False, error=f"Unknown tool: {name}")

    async def _spawn_agent(self, args: dict[str, Any], start: float) -> ToolResult:
        """Create a child agent, run it with the task, return result."""
        parent_id = args.get("agent_id")
        child_name = args["name"]
        task = args["task"]

        # Resolve child config
        parent = await self._agent_repo.get(parent_id) if parent_id else None
        child_config = AgentConfig()
        template = args.get("template")

        if template and self._resolve_prompt:
            # Templated spawn: load from prompts/{template}.md/.json
            child_config.system_prompt = self._resolve_prompt(template)
            if self._resolve_config:
                file_config = self._resolve_config(template)
                if file_config.model:
                    child_config.model = file_config.model
                if file_config.temperature is not None:
                    child_config.temperature = file_config.temperature
                if file_config.max_iterations is not None:
                    child_config.max_iterations = file_config.max_iterations
            # Fall back to parent for fields not set by template
            if parent:
                if child_config.model == AgentConfig().model:
                    child_config.model = parent.config.model
                if child_config.temperature == AgentConfig().temperature:
                    child_config.temperature = parent.config.temperature
        elif parent:
            # Ad-hoc spawn: inherit from parent
            child_config.model = parent.config.model
            child_config.temperature = parent.config.temperature

        # Explicit overrides from spawn call always win
        if "system_prompt" in args and args["system_prompt"]:
            child_config.system_prompt = args["system_prompt"]
        if "model" in args and args["model"]:
            child_config.model = args["model"]
        if "temperature" in args and args["temperature"] is not None:
            child_config.temperature = args["temperature"]

        # Disable auto_extract for sub-agents (keep it lightweight)
        child_config.auto_extract = False

        # Create child agent
        child = Agent(
            name=child_name,
            config=child_config,
            parent_agent_id=parent_id,
        )
        await self._agent_repo.create(child)

        # Emit AGENT_SPAWN event on parent
        if parent_id:
            await self._event_bus.emit(
                Event(
                    agent_id=parent_id,
                    event_type=EventType.AGENT_SPAWN,
                    module="tools.agent_spawner",
                    payload={
                        "child_agent_id": child.id,
                        "child_name": child_name,
                        "task": task[:200],
                    },
                )
            )

        # Run the child agent
        try:
            response = await self._run_child(child, task)
            duration = int((time.monotonic() - start) * 1000)

            # Emit AGENT_COMPLETE on child
            await self._event_bus.emit(
                Event(
                    agent_id=child.id,
                    event_type=EventType.AGENT_COMPLETE,
                    module="tools.agent_spawner",
                    payload={
                        "parent_agent_id": parent_id,
                        "content_preview": (
                            response.content[:200] if response.content else None
                        ),
                    },
                    duration_ms=duration,
                )
            )

            return ToolResult(
                success=True,
                output=json.dumps(
                    {
                        "child_agent_id": child.id,
                        "content": response.content,
                    }
                ),
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)

            # Emit ERROR on child
            await self._event_bus.emit(
                Event(
                    agent_id=child.id,
                    event_type=EventType.ERROR,
                    module="tools.agent_spawner",
                    payload={
                        "parent_agent_id": parent_id,
                        "error": str(e)[:200],
                    },
                    duration_ms=duration,
                )
            )

            # Update child status to FAILED
            child.status = AgentStatus.FAILED
            await self._agent_repo.update(child.id, child)

            return ToolResult(
                success=False,
                error=f"Child agent '{child_name}' failed: {e}",
                duration_ms=duration,
            )

    async def _run_child(self, child: Agent, task: str) -> AgentResponse:
        """Run a child agent's core loop inline."""
        # Minimal agent loop — no tool registry for children in Phase 1
        child.status = AgentStatus.RUNNING
        await self._agent_repo.update(child.id, child)

        conversation = Conversation(agent_id=child.id)
        await self._conv_repo.create(conversation)

        conversation.messages = [
            Message(role=MessageRole.SYSTEM, content=child.config.system_prompt),
            Message(role=MessageRole.HUMAN, content=task),
        ]

        llm_config = LLMConfig(
            model=child.config.model,
            temperature=child.config.temperature,
        )

        response: LLMResponse = await self._llm.complete(
            conversation.messages,
            tools=None,
            config=llm_config,
        )

        from datetime import UTC, datetime

        conversation.messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=response.content or "",
                timestamp=datetime.now(UTC).isoformat(),
            )
        )
        await self._conv_repo.update(conversation.id, conversation)

        child.status = AgentStatus.IDLE
        await self._agent_repo.update(child.id, child)

        return AgentResponse(
            agent_id=child.id,
            content=response.content,
            conversation_id=conversation.id,
        )

    async def _wait_for_agent(self, args: dict[str, Any], start: float) -> ToolResult:
        """Wait for a child agent to complete and return its result."""
        child_id = args["child_agent_id"]

        child = await self._agent_repo.get(child_id)
        if child is None:
            return ToolResult(
                success=False,
                error=f"Agent {child_id} not found",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # For synchronous spawn, child is already complete
        return await self._get_agent_result(args, start)

    async def _get_agent_result(self, args: dict[str, Any], start: float) -> ToolResult:
        """Get a child agent's current status and last response."""
        child_id = args["child_agent_id"]

        child = await self._agent_repo.get(child_id)
        if child is None:
            return ToolResult(
                success=False,
                error=f"Agent {child_id} not found",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # Get last assistant message from conversation
        content = None
        convos = await self._conv_repo.list(filters={"agent_id": child_id})
        if convos:
            for msg in reversed(convos[0].messages):
                if msg.role == MessageRole.ASSISTANT:
                    content = msg.content
                    break

        duration = int((time.monotonic() - start) * 1000)
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "child_agent_id": child.id,
                    "status": child.status.value,
                    "content": content,
                }
            ),
            duration_ms=duration,
        )

    async def _list_child_agents(
        self, args: dict[str, Any], start: float
    ) -> ToolResult:
        """List all children of the calling agent."""
        parent_id = args.get("agent_id")
        if not parent_id:
            return ToolResult(
                success=False,
                error="agent_id required",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        children = await self._agent_repo.list_children(parent_id)
        duration = int((time.monotonic() - start) * 1000)
        return ToolResult(
            success=True,
            output=json.dumps(
                [
                    {
                        "id": c.id,
                        "name": c.name,
                        "status": c.status.value,
                    }
                    for c in children
                ]
            ),
            duration_ms=duration,
        )
