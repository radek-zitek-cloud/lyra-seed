"""Application configuration via environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables with LYRA_ prefix."""

    model_config = {"env_prefix": "LYRA_"}

    openrouter_api_key: SecretStr = SecretStr("")
    default_model: str = "minimax/minimax-m2.7"
    db_path: str = "lyra.db"
    host: str = "0.0.0.0"
    port: int = 8000
