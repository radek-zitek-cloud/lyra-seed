"""FastAPI application factory."""

from fastapi import FastAPI

from agent_platform.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    app = FastAPI(title="Agent Platform", version="0.1.0")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
