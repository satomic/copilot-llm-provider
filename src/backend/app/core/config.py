"""
Application settings using pydantic-settings.

Loads configuration from environment variables and .env files.
All settings have sensible defaults for local development.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration.

    Settings are loaded in this priority order:
    1. Environment variables
    2. .env file
    3. Default values defined here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -- GitHub Authentication --
    # GitHub personal access token with Copilot access.
    # Falls back to GH_TOKEN / GITHUB_TOKEN env vars or stored OAuth if not set.
    github_token: str | None = None

    # -- Server Authentication --
    # Optional API key to protect server endpoints.
    # If not set, the server runs without authentication.
    api_key: str | None = None

    # -- Server Configuration --
    host: str = "0.0.0.0"
    port: int = 8000

    # Allowed CORS origins. Defaults to ["*"] (allow all).
    cors_origins: list[str] = ["*"]

    # Logging level: debug, info, warning, error, critical.
    log_level: str = "info"

    # -- Frontend --
    # Path to built frontend static files. Set to "frontend/dist" in production.
    # Leave empty in development to use the Vite dev server.
    frontend_dir: str | None = None
