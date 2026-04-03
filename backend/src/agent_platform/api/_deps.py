"""Dependency access for API routes — simple module-level references.

These are set during app startup and accessed by routes.
This avoids circular imports between routes and main.
"""

from collections.abc import Callable
from typing import Any

from agent_platform.core.runtime import AgentRuntime
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import (
    SqliteConversationRepo,
)
from agent_platform.observation.in_process_event_bus import (
    InProcessEventBus,
)
from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.skill_provider import SkillProvider
from agent_platform.tools.template_provider import TemplateProvider

_agent_repo: SqliteAgentRepo | None = None
_conversation_repo: SqliteConversationRepo | None = None
_event_bus: InProcessEventBus | None = None
_runtime: AgentRuntime | None = None
_skill_provider: SkillProvider | None = None
_template_provider: TemplateProvider | None = None
_tool_registry: ToolRegistry | None = None
_system_prompt_resolver: Callable[[str], str] | None = None
_agent_config_resolver: Callable | None = None
_default_model: str | None = None
_platform_config: Any = None
_project_root: Any = None
_memory_store: Any = None
_message_repo: Any = None


def configure(
    agent_repo: SqliteAgentRepo,
    conversation_repo: SqliteConversationRepo,
    event_bus: InProcessEventBus,
    runtime: AgentRuntime,
    skill_provider: SkillProvider | None = None,
    template_provider: TemplateProvider | None = None,
    tool_registry: ToolRegistry | None = None,
    system_prompt_resolver: Callable[[str], str] | None = None,
    agent_config_resolver: Callable | None = None,
    default_model: str | None = None,
    platform_config: Any = None,
    project_root: Any = None,
    memory_store: Any = None,
    message_repo: Any = None,
) -> None:
    global _agent_repo, _conversation_repo, _event_bus, _runtime
    global _skill_provider, _template_provider, _tool_registry
    global _system_prompt_resolver, _agent_config_resolver
    global _default_model
    global _memory_store, _message_repo
    global _platform_config, _project_root
    _agent_repo = agent_repo
    _conversation_repo = conversation_repo
    _event_bus = event_bus
    _runtime = runtime
    _skill_provider = skill_provider
    _template_provider = template_provider
    _tool_registry = tool_registry
    _system_prompt_resolver = system_prompt_resolver
    _agent_config_resolver = agent_config_resolver
    _default_model = default_model
    _platform_config = platform_config
    _project_root = project_root
    _memory_store = memory_store
    _message_repo = message_repo


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


def get_skill_provider() -> SkillProvider:
    assert _skill_provider is not None, "App not initialized"
    return _skill_provider


def get_template_provider() -> TemplateProvider:
    assert _template_provider is not None, "App not initialized"
    return _template_provider


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
    """Reload platform config from disk on every call."""
    if _project_root is not None:
        from agent_platform.core.platform_config import (
            load_platform_config,
        )

        return load_platform_config(_project_root)
    return _platform_config


def get_memory_store():
    assert _memory_store is not None, "App not initialized"
    return _memory_store


def get_message_repo():
    return _message_repo
