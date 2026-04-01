"""Dependency access for API routes — simple module-level references.

These are set during app startup and accessed by routes.
This avoids circular imports between routes and main.
"""

from agent_platform.core.runtime import AgentRuntime
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.observation.in_process_event_bus import InProcessEventBus

_agent_repo: SqliteAgentRepo | None = None
_conversation_repo: SqliteConversationRepo | None = None
_event_bus: InProcessEventBus | None = None
_runtime: AgentRuntime | None = None


def configure(
    agent_repo: SqliteAgentRepo,
    conversation_repo: SqliteConversationRepo,
    event_bus: InProcessEventBus,
    runtime: AgentRuntime,
) -> None:
    global _agent_repo, _conversation_repo, _event_bus, _runtime
    _agent_repo = agent_repo
    _conversation_repo = conversation_repo
    _event_bus = event_bus
    _runtime = runtime


def get_agent_repo() -> SqliteAgentRepo:
    assert _agent_repo is not None, "App not initialized"
    return _agent_repo


def get_conversation_repo() -> SqliteConversationRepo:
    assert _conversation_repo is not None, "App not initialized"
    return _conversation_repo


def get_event_bus() -> InProcessEventBus:
    assert _event_bus is not None, "App not initialized"
    return _event_bus


def get_runtime() -> AgentRuntime:
    assert _runtime is not None, "App not initialized"
    return _runtime
