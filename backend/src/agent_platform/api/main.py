"""FastAPI application factory."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_platform.api import _deps
from agent_platform.api.routes import router
from agent_platform.core.config import Settings
from agent_platform.core.runtime import AgentRuntime
from agent_platform.db.sqlite_agent_repo import SqliteAgentRepo
from agent_platform.db.sqlite_conversation_repo import SqliteConversationRepo
from agent_platform.llm.openrouter import OpenRouterProvider
from agent_platform.observation.in_process_event_bus import InProcessEventBus


def create_app(
    settings: Settings | None = None,
    db_dir: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    if db_dir is None:
        db_dir = os.path.dirname(settings.db_path) or "."

    event_bus = InProcessEventBus(
        db_path=os.path.join(db_dir, "events.db")
    )
    agent_repo = SqliteAgentRepo(
        os.path.join(db_dir, "agents.db")
    )
    conv_repo = SqliteConversationRepo(
        os.path.join(db_dir, "conversations.db")
    )

    llm_provider = OpenRouterProvider(
        api_key=settings.openrouter_api_key.get_secret_value(),
        event_bus=event_bus,
    )

    runtime = AgentRuntime(
        agent_repo=agent_repo,
        conversation_repo=conv_repo,
        llm_provider=llm_provider,
        event_bus=event_bus,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await event_bus.initialize()
        await agent_repo.initialize()
        await conv_repo.initialize()
        _deps.configure(agent_repo, conv_repo, event_bus, runtime)
        yield
        # Shutdown
        await event_bus.close()
        await agent_repo.close()
        await conv_repo.close()

    app = FastAPI(title="Agent Platform", version="0.1.0", lifespan=lifespan)

    app.state.event_bus = event_bus
    app.state.agent_repo = agent_repo
    app.state.conversation_repo = conv_repo
    app.state.runtime = runtime

    app.include_router(router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
