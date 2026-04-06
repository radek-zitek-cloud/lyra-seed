"""Agent runtime engine — core agent loop."""

import asyncio
import json
import logging
from datetime import UTC, datetime

from agent_platform.core.models import (
    Agent,
    AgentResponse,
    AgentStatus,
    Conversation,
    HITLPolicy,
)
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.llm.models import LLMConfig, LLMResponse, Message, MessageRole
from agent_platform.observation.events import Event, EventType
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Executes the core agent loop: prompt → LLM → tool calls → response."""

    def __init__(
        self,
        agent_repo: SqliteAgentRepo,
        conversation_repo: SqliteConversationRepo,
        llm_provider: object,  # LLMProvider protocol
        event_bus: InProcessEventBus,
        tool_registry: ToolRegistry | None = None,
        context_manager: object | None = None,
        extractor: object | None = None,
        message_repo: object | None = None,
    ) -> None:
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._llm = llm_provider
        self._event_bus = event_bus
        self._tool_registry = tool_registry or ToolRegistry()
        self._context_manager = context_manager
        self._extractor = extractor
        self._message_repo = message_repo
        self._hitl_pending: dict[str, asyncio.Event] = {}
        self._hitl_responses: dict[str, dict] = {}

    async def run(self, agent_id: str, human_message: str) -> AgentResponse:
        """Run the agent loop for a given agent and human message."""
        agent = await self._agent_repo.get(agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        # Set agent to RUNNING
        agent.status = AgentStatus.RUNNING
        await self._agent_repo.update(agent.id, agent)

        # Get or create conversation
        convos = await self._conv_repo.list(filters={"agent_id": agent_id})
        if convos:
            conversation = convos[0]
        else:
            conversation = Conversation(agent_id=agent_id)
            await self._conv_repo.create(conversation)

        # Add system prompt if conversation is empty
        if not conversation.messages:
            now = datetime.now(UTC)
            time_context = (
                f"\n\nCurrent date and time: "
                f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                f"({now.strftime('%A')})"
            )
            conversation.messages.append(
                Message(
                    role=MessageRole.SYSTEM,
                    content=agent.config.system_prompt + time_context,
                )
            )

        # Add human message
        conversation.messages.append(
            Message(
                role=MessageRole.HUMAN,
                content=human_message,
                timestamp=datetime.now(UTC).isoformat(),
            )
        )

        events_emitted = 0

        # Inject relevant memories into context
        if self._context_manager is not None:
            conversation.messages = await self._context_manager.assemble(
                agent_id=agent_id,
                messages=conversation.messages,
                query=human_message,
                top_k=agent.config.memory_top_k,
                max_context_tokens=agent.config.max_context_tokens,
            )
            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.MEMORY_READ,
                    module="core.runtime",
                    payload={"query": human_message},
                )
            )
            events_emitted += 1

        try:
            iteration = 0
            while iteration < agent.config.max_iterations:
                iteration += 1

                # Inject pending GUIDANCE messages
                await self._inject_guidance(agent_id, conversation)

                # Call LLM with tool list
                llm_config = LLMConfig(
                    model=agent.config.model,
                    temperature=agent.config.temperature,
                )
                tools_schema = await self._tool_registry.get_tools_schema(
                    allowed_mcp_servers=agent.config.allowed_mcp_servers,
                    allowed_tools=agent.config.allowed_tools or None,
                )

                # Set agent_id and retry config on providers
                if hasattr(self._llm, "_current_agent_id"):
                    self._llm._current_agent_id = agent_id
                if hasattr(self._llm, "_current_retry"):
                    rc = agent.config.retry
                    self._llm._current_retry = {
                        k: v
                        for k, v in {
                            "max_retries": rc.max_retries,
                            "base_delay": rc.base_delay,
                            "max_delay": rc.max_delay,
                        }.items()
                        if v is not None
                    } or None
                self._set_embedding_agent_id(agent_id)

                # Propagate LLM config to tool providers that need it
                self._tool_registry.set_provider_config("_llm_config", llm_config)

                response: LLMResponse = await self._llm.complete(
                    conversation.messages,
                    tools=tools_schema or None,
                    config=llm_config,
                )

                events_emitted += 1  # provider emits LLM_REQUEST + LLM_RESPONSE

                # If no tool calls, we have our final response
                if not response.tool_calls:
                    conversation.messages.append(
                        Message(
                            role=MessageRole.ASSISTANT,
                            content=response.content or "",
                            timestamp=datetime.now(UTC).isoformat(),
                        )
                    )
                    await self._conv_repo.update(conversation.id, conversation)
                    agent.status = AgentStatus.IDLE
                    await self._agent_repo.update(agent.id, agent)

                    # Reset LLM agent context so extraction/pruning
                    # tokens don't stream to the agent's UI
                    if hasattr(self._llm, "_current_agent_id"):
                        self._llm._current_agent_id = "system"

                    # Auto-extract facts from the response
                    await self._auto_extract(
                        agent_id,
                        response.content or "",
                        conversation.messages,
                        agent.config,
                    )

                    # Prune stale memories after successful run
                    await self._prune_memories(agent_id, agent.config)

                    return AgentResponse(
                        agent_id=agent_id,
                        content=response.content,
                        conversation_id=conversation.id,
                        events_emitted=events_emitted,
                    )

                # Handle tool calls
                conversation.messages.append(
                    Message(
                        role=MessageRole.ASSISTANT,
                        content=response.content or "",
                        tool_calls=response.tool_calls,
                        timestamp=datetime.now(UTC).isoformat(),
                    )
                )

                for tool_call in response.tool_calls:
                    # HITL check
                    if agent.config.hitl_policy == HITLPolicy.ALWAYS_ASK:
                        approved = await self._hitl_gate(
                            agent, tool_call.name, tool_call.arguments
                        )
                        if not approved:
                            # Tool denied
                            await self._event_bus.emit(
                                Event(
                                    agent_id=agent_id,
                                    event_type=EventType.TOOL_RESULT,
                                    module="core.runtime",
                                    payload={
                                        "tool_name": tool_call.name,
                                        "denied": True,
                                    },
                                )
                            )
                            events_emitted += 1
                            conversation.messages.append(
                                Message(
                                    role=MessageRole.TOOL_RESULT,
                                    content=f"Tool '{tool_call.name}' "
                                    "was denied by the human.",
                                    tool_call_id=tool_call.id,
                                    timestamp=datetime.now(UTC).isoformat(),
                                )
                            )
                            continue

                    # Emit TOOL_CALL event
                    await self._event_bus.emit(
                        Event(
                            agent_id=agent_id,
                            event_type=EventType.TOOL_CALL,
                            module="core.runtime",
                            payload={
                                "tool_name": tool_call.name,
                                "arguments": tool_call.arguments,
                            },
                        )
                    )
                    events_emitted += 1

                    # Inject agent_id for all tool calls
                    # (harmless for tools that don't use it,
                    # required for skills, memory, spawner, etc.)
                    call_args = dict(tool_call.arguments)
                    call_args["agent_id"] = agent_id

                    # Execute tool via registry
                    result = await self._tool_registry.call_tool(
                        tool_call.name, call_args
                    )
                    tool_result = (
                        result.output if result.success else f"Error: {result.error}"
                    )
                    if isinstance(tool_result, dict):
                        tool_result = json.dumps(tool_result)

                    # Emit TOOL_RESULT event
                    await self._event_bus.emit(
                        Event(
                            agent_id=agent_id,
                            event_type=EventType.TOOL_RESULT,
                            module="core.runtime",
                            payload={
                                "tool_name": tool_call.name,
                                "result": tool_result,
                                "success": result.success,
                                "duration_ms": result.duration_ms,
                            },
                            duration_ms=result.duration_ms,
                        )
                    )
                    events_emitted += 1

                    conversation.messages.append(
                        Message(
                            role=MessageRole.TOOL_RESULT,
                            content=tool_result,
                            tool_call_id=tool_call.id,
                            timestamp=datetime.now(UTC).isoformat(),
                        )
                    )

                await self._conv_repo.update(conversation.id, conversation)

            # Max iterations reached
            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.ERROR,
                    module="core.runtime",
                    payload={
                        "error": "max_iterations_reached",
                        "iterations": iteration,
                        "max_iterations": agent.config.max_iterations,
                    },
                )
            )
            events_emitted += 1

            agent.status = AgentStatus.IDLE
            await self._agent_repo.update(agent.id, agent)

            return AgentResponse(
                agent_id=agent_id,
                content=(
                    f"Stopped: maximum iterations "
                    f"({agent.config.max_iterations}) reached."
                ),
                conversation_id=conversation.id,
                events_emitted=events_emitted,
            )

        except Exception as e:
            agent.status = AgentStatus.FAILED
            await self._agent_repo.update(agent.id, agent)

            await self._event_bus.emit(
                Event(
                    agent_id=agent_id,
                    event_type=EventType.ERROR,
                    module="core.runtime",
                    payload={"error": str(e)},
                )
            )
            raise

    async def _hitl_gate(
        self,
        agent: Agent,
        tool_name: str,
        tool_args: dict,
    ) -> bool:
        """Pause execution for HITL approval. Returns True if approved."""
        # Set agent to WAITING_HITL
        agent.status = AgentStatus.WAITING_HITL
        await self._agent_repo.update(agent.id, agent)

        # Emit HITL_REQUEST
        await self._event_bus.emit(
            Event(
                agent_id=agent.id,
                event_type=EventType.HITL_REQUEST,
                module="core.runtime",
                payload={
                    "tool_name": tool_name,
                    "arguments": tool_args,
                },
            )
        )

        # Wait for response with timeout
        gate = asyncio.Event()
        self._hitl_pending[agent.id] = gate
        try:
            await asyncio.wait_for(
                gate.wait(),
                timeout=agent.config.hitl_timeout_seconds,
            )
        except TimeoutError:
            # HITL timed out — treat as denial
            self._hitl_pending.pop(agent.id, None)
            self._hitl_responses.pop(agent.id, None)
            agent.status = AgentStatus.IDLE
            await self._agent_repo.update(agent.id, agent)
            await self._event_bus.emit(
                Event(
                    agent_id=agent.id,
                    event_type=EventType.HITL_RESPONSE,
                    module="core.runtime",
                    payload={
                        "approved": False,
                        "timed_out": True,
                    },
                )
            )
            return False

        response = self._hitl_responses.pop(agent.id, {"approved": False})
        del self._hitl_pending[agent.id]

        # Restore agent to RUNNING
        agent.status = AgentStatus.RUNNING
        await self._agent_repo.update(agent.id, agent)

        # Emit HITL_RESPONSE
        await self._event_bus.emit(
            Event(
                agent_id=agent.id,
                event_type=EventType.HITL_RESPONSE,
                module="core.runtime",
                payload=response,
            )
        )

        return response.get("approved", False)

    async def hitl_respond(
        self,
        agent_id: str,
        approved: bool,
        message: str | None = None,
    ) -> bool:
        """Respond to a pending HITL gate."""
        gate = self._hitl_pending.get(agent_id)
        if gate is None:
            return False

        self._hitl_responses[agent_id] = {
            "approved": approved,
            "message": message,
        }
        gate.set()
        return True

    def _set_embedding_agent_id(self, agent_id: str) -> None:
        """Propagate agent_id to the embedding provider for event attribution."""
        if self._context_manager is None:
            return
        store = getattr(self._context_manager, "_store", None)
        if store is None:
            return
        emb_fn = getattr(store, "embedding_fn", None)
        if emb_fn is not None and hasattr(emb_fn, "set_agent_id"):
            emb_fn.set_agent_id(agent_id)

    async def _inject_guidance(self, agent_id: str, conversation: Conversation) -> None:
        """Inject all pending messages into conversation context."""
        if self._message_repo is None:
            return
        try:
            msgs = await self._message_repo.list_for_agent(
                agent_id,
                direction="inbox",
            )
            for msg in msgs:
                text = (
                    f"[{msg.message_type.value} from "
                    f"{msg.from_agent_id}]: {msg.content}"
                )
                conversation.messages.append(
                    Message(role=MessageRole.SYSTEM, content=text)
                )
                # Delete after injection so it's not re-injected
                await self._message_repo.delete(msg.id)
        except Exception:
            logger.warning(
                "Failed to inject guidance messages for %s", agent_id, exc_info=True
            )

    async def _auto_extract(
        self,
        agent_id: str,
        content: str,
        messages: list,
        config: object,
    ) -> None:
        """Run automatic fact extraction if enabled."""
        if not getattr(config, "auto_extract", False):
            return
        if self._extractor is None:
            return
        try:
            await self._extractor.extract(
                agent_id=agent_id,
                assistant_message=content,
                conversation_context=messages,
                memory_sharing=getattr(config, "memory_sharing", None),
                extraction_model=getattr(config, "extraction_model", None),
            )
        except Exception:
            logger.warning("Fact extraction failed for %s", agent_id, exc_info=True)

    async def _prune_memories(
        self, agent_id: str, agent_config: object | None = None
    ) -> None:
        """Prune stale memories after a successful agent run."""
        if self._context_manager is None:
            return
        store = getattr(self._context_manager, "_store", None)
        if store is None or not hasattr(store, "prune"):
            return
        threshold = getattr(agent_config, "prune_threshold", 0.1)
        max_entries = getattr(agent_config, "prune_max_entries", 500)
        try:
            deleted = await store.prune(
                agent_id, threshold=threshold, max_entries=max_entries
            )
            if deleted > 0:
                await self._event_bus.emit(
                    Event(
                        agent_id=agent_id,
                        event_type=EventType.MEMORY_WRITE,
                        module="core.runtime",
                        payload={
                            "action": "gc_archive",
                            "archived_count": deleted,
                        },
                    )
                )
        except Exception:
            logger.warning("Memory GC failed for %s", agent_id, exc_info=True)

    async def cleanup_stuck_agents(self) -> int:
        """Reset agents stuck in RUNNING/WAITING_HITL to IDLE.

        Called on startup to recover from crashes.
        """
        count = 0
        all_agents = await self._agent_repo.list()
        for agent in all_agents:
            if agent.status in (
                AgentStatus.RUNNING,
                AgentStatus.WAITING_HITL,
            ):
                agent.status = AgentStatus.IDLE
                await self._agent_repo.update(agent.id, agent)
                count += 1
        if count:
            logger.info("Cleaned up %d stuck agents", count)
        return count
