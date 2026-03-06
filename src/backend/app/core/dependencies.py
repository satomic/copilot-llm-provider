"""
FastAPI dependency injection functions.

Provides shared dependencies that are injected into route handlers
via FastAPI's Depends() mechanism. This is the glue layer that connects
routes to configuration and providers without direct imports.
"""

import logging
from functools import lru_cache

from fastapi import HTTPException, Request

from src.backend.app.core.config import Settings
from src.backend.app.providers.base import Provider

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
    """Return an LLM provider instance.

    Uses the token pool for round-robin selection among active tokens.
    Falls back to the primary provider stored on app.state.

    Args:
        request: The incoming FastAPI request (injected automatically).

    Returns:
        The active Provider instance.

    Raises:
        HTTPException: 503 if no provider is available.
    """
    from src.backend.app.services.token_pool import get_token_pool

    # Check for explicit token selection via header
    requested_token_id = request.headers.get("X-GitHub-Token-Id")

    pool = get_token_pool()
    token_info = pool.select_token(requested_token_id)

    if token_info and token_info.provider:
        # Store selected token info on request state for downstream use
        request.state.github_token_id = token_info.id
        request.state.github_token_alias = token_info.alias
        return token_info.provider

    # Fallback to the primary provider
    provider: Provider | None = getattr(request.app.state, "provider", None)

    if provider is None:
        logger.error("No provider available — the app may still be starting up")
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "message": "Service unavailable. No LLM provider is available.",
                    "type": "server_error",
                    "code": 503,
                }
            },
        )

    request.state.github_token_id = None
    request.state.github_token_alias = None
    return provider
