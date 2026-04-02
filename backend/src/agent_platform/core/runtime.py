"""Agent runtime engine — core agent loop."""

import asyncio

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
    ) -> None:
        self._agent_repo = agent_repo
        self._conv_repo = conversation_repo
        self._llm = llm_provider
        self._event_bus = event_bus
        self._tool_registry = tool_registry or ToolRegistry()
        self._context_manager = context_manager
        self._extractor = extractor
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
            conversation.messages.append(
                Message(
                    role=MessageRole.SYSTEM,
                    content=agent.config.system_prompt,
                )
            )

        # Add human message
        from datetime import UTC, datetime

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

                # Call LLM with tool list
                llm_config = LLMConfig(
                    model=agent.config.model,
                    temperature=agent.config.temperature,
                )
                tools_schema = await self._tool_registry.get_tools_schema()

                # Emit LLM_REQUEST event
                await self._event_bus.emit(
                    Event(
                        agent_id=agent_id,
                        event_type=EventType.LLM_REQUEST,
                        module="core.runtime",
                        payload={
                            "iteration": iteration,
                            "model": agent.config.model,
                            "message_count": len(conversation.messages),
                            "tool_count": len(tools_schema),
                        },
                    )
                )
                events_emitted += 1

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

                response: LLMResponse = await self._llm.complete(
                    conversation.messages,
                    tools=tools_schema or None,
                    config=llm_config,
                )

                # Compute cost for this call
                from agent_platform.observation.cost_tracker import (
                    _get_cost_per_million,
                )

                _usage = response.usage or {}
                _prompt_tok = _usage.get("prompt_tokens", 0) or 0
                _compl_tok = _usage.get("completion_tokens", 0) or 0
                _in_rate, _out_rate = _get_cost_per_million(llm_config.model)
                _cost = (
                    _prompt_tok / 1_000_000 * _in_rate
                    + _compl_tok / 1_000_000 * _out_rate
                )

                # Emit LLM_RESPONSE event
                await self._event_bus.emit(
                    Event(
                        agent_id=agent_id,
                        event_type=EventType.LLM_RESPONSE,
                        module="core.runtime",
                        payload={
                            "iteration": iteration,
                            "has_content": response.content is not None,
                            "content_preview": (
                                response.content[:200] if response.content else None
                            ),
                            "tool_call_count": len(response.tool_calls),
                            "tool_calls": [tc.name for tc in response.tool_calls],
                            "usage": response.usage,
                            "model": llm_config.model,
                            "cost_usd": round(_cost, 6),
                        },
                    )
                )
                events_emitted += 1

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

                    # Inject agent_id for memory and spawner tools
                    # (always override — LLM may hallucinate the name instead of UUID)
                    call_args = dict(tool_call.arguments)
                    if tool_call.name in (
                        "remember", "recall", "forget",
                        "spawn_agent", "wait_for_agent",
                        "get_agent_result", "list_child_agents",
                    ):
                        call_args["agent_id"] = agent_id

                    # Execute tool via registry
                    result = await self._tool_registry.call_tool(
                        tool_call.name, call_args
                    )
                    tool_result = (
                        result.output if result.success else f"Error: {result.error}"
                    )
                    if isinstance(tool_result, dict):
                        import json

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
            )
        except Exception:
            pass  # Extraction failure never breaks the run

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
                            "action": "gc_prune",
                            "deleted_count": deleted,
                        },
                    )
                )
        except Exception:
            pass  # GC failure should not break the run

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
            import logging

            logging.getLogger(__name__).info("Cleaned up %d stuck agents", count)
        return count
