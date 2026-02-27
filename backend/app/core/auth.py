"""
Authentication utilities.

Provides FastAPI dependency functions for API key verification.
Supports X-API-Key header and Bearer token authentication.
"""

import logging

from fastapi import HTTPException, Request

from backend.app.core.dependencies import get_settings

logger = logging.getLogger(__name__)


async def verify_api_key(request: Request) -> str | None:
    """FastAPI dependency that verifies the API key from the request.

    Checks for an API key in the following locations (in order):
    1. X-API-Key header
    2. Authorization header (Bearer token)

    If the server is configured without an API key (api_key is None),
    authentication is bypassed (suitable for local development).

    Args:
        request: The incoming FastAPI request.

    Returns:
        The validated API key string, or None if auth is disabled.

    Raises:
        HTTPException: 401 if the API key is missing or invalid.
    """
    settings = get_settings()

    # If no API key is configured, skip authentication entirely
    if not settings.api_key:
        return None

    # Try X-API-Key header first
    api_key = request.headers.get("x-api-key")

    # Fall back to Authorization: Bearer <key>
    if not api_key:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            api_key = auth_header[7:].strip()

    # No key provided at all
    if not api_key:
        logger.warning("Request missing API key from %s", request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Missing API key. Provide it via X-API-Key header or Authorization: Bearer <key>.",
                    "type": "authentication_error",
                    "code": 401,
                }
            },
        )

    # Key provided but does not match
    if api_key != settings.api_key:
        logger.warning("Invalid API key attempt from %s", request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid API key.",
                    "type": "authentication_error",
                    "code": 401,
                }
            },
        )

    return api_key
