"""
FastAPI dependency injection functions.

Provides shared dependencies that are injected into route handlers
via FastAPI's Depends() mechanism. This is the glue layer that connects
routes to configuration and providers without direct imports.
"""

import logging
from functools import lru_cache

from fastapi import HTTPException, Request

from backend.app.core.config import Settings
from backend.app.providers.base import Provider

logger = logging.getLogger(__name__)


@lru_cache
def get_settings() -> Settings:
    """Return the application settings singleton.

    Uses lru_cache to ensure a single Settings instance is created
    and reused across all requests.

    Returns:
        The application Settings instance.
    """
    return Settings()


async def get_provider(request: Request) -> Provider:
    """Return the active LLM provider instance.

    This dependency is resolved at request time and returns the
    concrete Provider implementation (e.g., CopilotProvider) that
    was initialized during application startup and stored on
    ``app.state.provider``.

    Args:
        request: The incoming FastAPI request (injected automatically).

    Returns:
        The active Provider instance.

    Raises:
        HTTPException: 503 if the provider is not initialized.
    """
    provider: Provider | None = getattr(request.app.state, "provider", None)

    if provider is None:
        logger.error("Provider not initialized — the app may still be starting up")
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "message": "Service unavailable. The LLM provider is not initialized.",
                    "type": "server_error",
                    "code": 503,
                }
            },
        )

    return provider
