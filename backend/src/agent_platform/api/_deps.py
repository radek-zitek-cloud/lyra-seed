"""Dependency access for API routes — simple module-level references.

These are set during app startup and accessed by routes.
This avoids circular imports between routes and main.
"""

from collections.abc import Callable
from typing import Any

from agent_platform.core.runtime import AgentRuntime
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_macro_repo import SqliteMacroRepo
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.prompt_macro import PromptMacroProvider
from agent_platform.tools.registry import ToolRegistry

_agent_repo: SqliteAgentRepo | None = None
_conversation_repo: SqliteConversationRepo | None = None
_event_bus: InProcessEventBus | None = None
_runtime: AgentRuntime | None = None
_macro_repo: SqliteMacroRepo | None = None
_macro_provider: PromptMacroProvider | None = None
_tool_registry: ToolRegistry | None = None
_system_prompt_resolver: Callable[[str], str] | None = None
_agent_config_resolver: Callable | None = None
_default_model: str | None = None
_platform_config: Any = None


def configure(
    agent_repo: SqliteAgentRepo,
    conversation_repo: SqliteConversationRepo,
    event_bus: InProcessEventBus,
    runtime: AgentRuntime,
    macro_repo: SqliteMacroRepo | None = None,
    macro_provider: PromptMacroProvider | None = None,
    tool_registry: ToolRegistry | None = None,
    system_prompt_resolver: Callable[[str], str] | None = None,
    agent_config_resolver: Callable | None = None,
    default_model: str | None = None,
    platform_config: Any = None,
) -> None:
    global _agent_repo, _conversation_repo, _event_bus, _runtime
    global _macro_repo, _macro_provider, _tool_registry
    global _system_prompt_resolver, _agent_config_resolver, _default_model
    global _platform_config
    _agent_repo = agent_repo
    _conversation_repo = conversation_repo
    _event_bus = event_bus
    _runtime = runtime
    _macro_repo = macro_repo
    _macro_provider = macro_provider
    _tool_registry = tool_registry
    _system_prompt_resolver = system_prompt_resolver
    _agent_config_resolver = agent_config_resolver
    _default_model = default_model
    _platform_config = platform_config


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


def get_macro_repo() -> SqliteMacroRepo:
    assert _macro_repo is not None, "App not initialized"
    return _macro_repo


def get_macro_provider() -> PromptMacroProvider:
    assert _macro_provider is not None, "App not initialized"
    return _macro_provider


def get_tool_registry() -> ToolRegistry:
    assert _tool_registry is not None, "App not initialized"
    return _tool_registry


def get_system_prompt_resolver() -> Callable[[str], str]:
    assert _system_prompt_resolver is not None, "App not initialized"
    return _system_prompt_resolver


def get_agent_config_resolver() -> Callable:
    assert _agent_config_resolver is not None, "App not initialized"
    return _agent_config_resolver


def get_default_model() -> str:
    return _default_model or "openai/gpt-4.1-mini"


def get_platform_config():
    return _platform_config
