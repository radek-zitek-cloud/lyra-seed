"""FastAPI application factory."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_platform.api import _deps
from agent_platform.api.macro_routes import router as macro_router
from agent_platform.api.observation_routes import router as observation_router
from agent_platform.api.routes import router
from agent_platform.api.ws_routes import router as ws_router
from agent_platform.core.config import Settings
from agent_platform.core.runtime import AgentRuntime
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.db.sqlite_macro_repo import SqliteMacroRepo
from agent_platform.llm.openrouter import OpenRouterProvider
from agent_platform.observation.in_process_event_bus import InProcessEventBus
from agent_platform.tools.prompt_macro import PromptMacroProvider
from agent_platform.tools.registry import ToolRegistry


def create_app(
    settings: Settings | None = None,
    db_dir: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    if db_dir is None:
        db_dir = os.path.dirname(settings.db_path) or "."

    event_bus = InProcessEventBus(db_path=os.path.join(db_dir, "events.db"))
    agent_repo = SqliteAgentRepo(os.path.join(db_dir, "agents.db"))
    conv_repo = SqliteConversationRepo(os.path.join(db_dir, "conversations.db"))
    macro_repo = SqliteMacroRepo(os.path.join(db_dir, "macros.db"))

    llm_provider = OpenRouterProvider(
        api_key=settings.openrouter_api_key.get_secret_value(),
        event_bus=event_bus,
    )

    # Tool system
    macro_provider = PromptMacroProvider(llm_provider=llm_provider)
    tool_registry = ToolRegistry()
    tool_registry.register_provider(macro_provider)

    runtime = AgentRuntime(
        agent_repo=agent_repo,
        conversation_repo=conv_repo,
        llm_provider=llm_provider,
        event_bus=event_bus,
        tool_registry=tool_registry,
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

        _deps.configure(
            agent_repo,
            conv_repo,
            event_bus,
            runtime,
            macro_repo=macro_repo,
            macro_provider=macro_provider,
            tool_registry=tool_registry,
        )
        yield
        # Shutdown
        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()
        await macro_repo.close()

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
