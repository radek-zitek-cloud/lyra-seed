"""FastAPI application factory."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_platform.api import _deps
from agent_platform.api.macro_routes import router as macro_router
from agent_platform.api.observation_routes import router as observation_router
from agent_platform.api.routes import router
from agent_platform.api.ws_routes import router as ws_router
from agent_platform.core.config import Settings
from agent_platform.core.platform_config import (
    load_platform_config,
    resolve_agent_config,
    resolve_system_prompt,
)
from agent_platform.core.runtime import AgentRuntime
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_macro_repo import SqliteMacroRepo
from agent_platform.llm.openrouter import OpenRouterProvider
from agent_platform.memory.chroma_memory_store import ChromaMemoryStore
from agent_platform.memory.context_manager import ContextManager
from agent_platform.memory.memory_tools import MemoryToolProvider
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.mcp_client import MCPClientProvider, MCPStdioClient
from agent_platform.tools.prompt_macro import PromptMacroProvider
from agent_platform.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Resolve project root (parent of backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


async def _shutdown(
    event_bus, mcp_provider, agent_repo, conv_repo, macro_repo, *, has_mcp
):
    """Shut down all resources. Called with a timeout wrapper."""
    # Close event bus first to unblock WebSocket subscribers
    await event_bus.close()
    if has_mcp:
        await mcp_provider.close_all()
    await agent_repo.close()
    await conv_repo.close()
    await macro_repo.close()


def create_app(
    settings: Settings | None = None,
    db_dir: str | None = None,
    project_root: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    if project_root is None:
        project_root = _PROJECT_ROOT

    # Load platform config (lyra.config.json)
    platform_config = load_platform_config(project_root)

    # Resolve data directory
    if db_dir is None:
        data_dir_cfg = Path(platform_config.dataDir)
        if not data_dir_cfg.is_absolute():
            data_dir_cfg = project_root / data_dir_cfg
        db_dir = str(data_dir_cfg)
    os.makedirs(db_dir, exist_ok=True)

    # Single consolidated database
    db_path = os.path.join(db_dir, "lyra.db")

    event_bus = InProcessEventBus(db_path=db_path)
    agent_repo = SqliteAgentRepo(db_path)
    conv_repo = SqliteConversationRepo(db_path)
    macro_repo = SqliteMacroRepo(db_path)

    llm_provider = OpenRouterProvider(
        api_key=settings.openrouter_api_key.get_secret_value(),
        event_bus=event_bus,
    )

    # Tool system
    macro_provider = PromptMacroProvider(llm_provider=llm_provider)
    tool_registry = ToolRegistry()
    tool_registry.register_provider(macro_provider)

    # MCP servers from config
    mcp_provider = MCPClientProvider()
    for name, server_cfg in platform_config.mcpServers.items():
        client = MCPStdioClient(
            server_name=name,
            command=server_cfg.command,
            args=server_cfg.args,
            env=server_cfg.env,
        )
        mcp_provider.add_client(client)

    if platform_config.mcpServers:
        tool_registry.register_provider(mcp_provider)

    # Memory system
    memory_dir = os.path.join(db_dir, "memory")
    os.makedirs(memory_dir, exist_ok=True)
    memory_store = ChromaMemoryStore(persist_dir=memory_dir)
    memory_provider = MemoryToolProvider(memory_store=memory_store, event_bus=event_bus)
    tool_registry.register_provider(memory_provider)
    context_manager = ContextManager(memory_store=memory_store, top_k=5)

    # System prompt resolver
    prompt_resolver = partial(
        resolve_system_prompt,
        prompts_dir=platform_config.systemPromptsDir,
        project_root=project_root,
    )

    config_resolver = partial(
        resolve_agent_config,
        prompts_dir=platform_config.systemPromptsDir,
        project_root=project_root,
    )

    runtime = AgentRuntime(
        agent_repo=agent_repo,
        conversation_repo=conv_repo,
        llm_provider=llm_provider,
        event_bus=event_bus,
        tool_registry=tool_registry,
        context_manager=context_manager,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await event_bus.initialize()
        await agent_repo.initialize()
        await conv_repo.initialize()
        await macro_repo.initialize()

        # Load macros from DB into provider
        macros = await macro_repo.list()
        for macro in macros:
            macro_provider.add_macro(macro)

        # Connect MCP servers
        if platform_config.mcpServers:
            logger.info("Connecting %d MCP servers...", len(platform_config.mcpServers))
            await mcp_provider.connect_all()

        _deps.configure(
            agent_repo,
            conv_repo,
            event_bus,
            runtime,
            macro_repo=macro_repo,
            macro_provider=macro_provider,
            tool_registry=tool_registry,
            system_prompt_resolver=prompt_resolver,
            agent_config_resolver=config_resolver,
            default_model=platform_config.defaultModel,
        )
        yield
        # Shutdown — with timeout to prevent hanging on reload
        logger.info("Shutting down...")
        try:
            await asyncio.wait_for(
                _shutdown(
                    event_bus,
                    mcp_provider,
                    agent_repo,
                    conv_repo,
                    macro_repo,
                    has_mcp=bool(platform_config.mcpServers),
                ),
                timeout=10.0,
            )
        except TimeoutError:
            logger.warning("Shutdown timed out after 10s, forcing exit")

    app = FastAPI(title="Agent Platform", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.event_bus = event_bus
    app.state.agent_repo = agent_repo
    app.state.conversation_repo = conv_repo
    app.state.runtime = runtime
    app.state.tool_registry = tool_registry

    app.include_router(router)
    app.include_router(macro_router)
    app.include_router(observation_router)
    app.include_router(ws_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
