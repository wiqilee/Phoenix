"""Configuration management for Phoenix Agent."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    """Walk up from CWD to find the nearest .env file."""
    current = Path.cwd()
    for _ in range(6):  # don't climb forever
        candidate = current / ".env"
        if candidate.is_file():
            return str(candidate)
        if current.parent == current:
            break
        current = current.parent
    return ".env"  # fallback


class Settings(BaseSettings):
    """All runtime configuration for the agent service.

    Values are loaded from environment variables. See `.env.example` for
    the complete list and what each one does.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google Cloud
    gcp_project_id: str = "phoenix-local"
    gcp_region: str = "us-central1"

    # Vertex AI / Gemini
    gemini_model: str = "gemini-3-flash"
    agent_builder_location: str = "us-central1"

    # GitLab
    gitlab_token: str = ""
    gitlab_base_url: str = "https://gitlab.com"
    gitlab_webhook_secret: str = "change-me"

    # Agent behavior
    agent_confidence_threshold: float = 0.7
    max_retry_strategies: int = 3
    sandbox_timeout_seconds: int = 300

    # Services
    parser_url: str = "http://parser:8001"

    # Firestore
    firestore_collection_prefix: str = "phoenix"

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get the singleton settings instance."""
    return Settings(_env_file=_find_env_file())


settings = get_settings()
