"""Application configuration via environment variables."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings

# Resolve .env from the project root (parent of backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables with LYRA_ prefix."""

    model_config = {
        "env_prefix": "LYRA_",
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
    }

    openrouter_api_key: SecretStr = SecretStr("")
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
