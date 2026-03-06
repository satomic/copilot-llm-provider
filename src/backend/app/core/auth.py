"""
Authentication utilities.

Provides FastAPI dependency functions for API key and session token verification.
Supports three authentication methods:
1. Web UI session tokens (from user login)
2. Managed API keys (with aliases, permissions, limits)
3. Legacy environment/runtime API key (backward compatibility)
"""

import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request

from src.backend.app.core.dependencies import get_settings
from src.backend.app.core.runtime_config import get_runtime_config
from src.backend.app.services.api_key_store import get_api_key_store
from src.backend.app.services.user_store import get_user_store

logger = logging.getLogger(__name__)


@dataclass
class AuthInfo:
    """Authentication result containing identity information."""

    auth_type: str  # "session" | "api_key" | "legacy" | "none"
    key_alias: str | None = None
    username: str | None = None
    api_key: str | None = None  # The raw key (for recording usage)


async def verify_api_key(request: Request) -> AuthInfo:
    """FastAPI dependency that verifies authentication.

    Checks for credentials in the following order:
    1. Session token (from user login) - full access
    2. Managed API key (from api_key_store) - restricted access
    3. Legacy API key (env/runtime config) - full access
    4. No auth configured - open access

    Returns:
        AuthInfo with authentication details.

    Raises:
        HTTPException: 401 if authentication fails.
    """
    # Extract token from headers
    token = _extract_token(request)

    # 1. Check if it's a session token
    if token:
        user_store = get_user_store()
        username = user_store.validate_session(token)
        if username:
            return AuthInfo(auth_type="session", username=username)

    # 2. Check if it's a managed API key
    if token:
        key_store = get_api_key_store()
        key_info = key_store.validate_key(token)
        if key_info:
            return AuthInfo(
                auth_type="api_key",
                key_alias=key_info.alias,
                api_key=token,
            )

    # 3. Check legacy API key (env var / runtime config)
    settings = get_settings()
    runtime_config = get_runtime_config()
    effective_key = runtime_config.api_key or settings.api_key

    if effective_key:
        if token and token == effective_key:
            return AuthInfo(auth_type="legacy")
        # Auth is required but no valid token provided
        if not token:
            logger.warning(
                "Request missing credentials from %s",
                request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "Authentication required. Provide a session token or API key via Authorization: Bearer <token>.",
                        "type": "authentication_error",
                        "code": 401,
                    }
                },
            )
        # Token provided but doesn't match anything
        logger.warning(
            "Invalid credentials from %s",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid credentials.",
                    "type": "authentication_error",
                    "code": 401,
                }
            },
        )

    # 4. Check if managed API keys or users exist (require auth even without legacy key)
    key_store = get_api_key_store()
    user_store = get_user_store()
    if key_store.has_keys() or user_store.has_users():
        if not token:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "Authentication required.",
                        "type": "authentication_error",
                        "code": 401,
                    }
                },
            )
        # Token provided but doesn't match anything
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid credentials.",
                    "type": "authentication_error",
                    "code": 401,
                }
            },
        )

    # No auth configured at all
    return AuthInfo(auth_type="none")


def check_model_permission(auth: AuthInfo, model: str) -> None:
    """Check if the authenticated user has permission to use a model.

    Raises HTTPException 403 if not allowed.
    """
    if auth.auth_type != "api_key" or not auth.api_key:
        return  # Session tokens and legacy keys have full access

    key_store = get_api_key_store()
    if not key_store.check_model_permission(auth.api_key, model):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "message": f"API key '{auth.key_alias}' does not have permission to use model '{model}'.",
                    "type": "permission_error",
                    "code": 403,
                }
            },
        )


def check_usage_limits(auth: AuthInfo, is_premium: bool = False) -> None:
    """Check if the authenticated user has remaining quota.

    Raises HTTPException 429 if limits exceeded.
    """
    if auth.auth_type != "api_key" or not auth.api_key:
        return  # Session tokens and legacy keys have no limits

    key_store = get_api_key_store()
    if not key_store.check_limits(auth.api_key, is_premium):
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "message": f"API key '{auth.key_alias}' has exceeded its usage limit.",
                    "type": "rate_limit_error",
                    "code": 429,
                }
            },
        )


def record_api_key_usage(auth: AuthInfo, is_premium: bool = False) -> None:
    """Record usage for a managed API key."""
    if auth.auth_type != "api_key" or not auth.api_key:
        return
    key_store = get_api_key_store()
    key_store.record_usage(auth.api_key, is_premium)


def _extract_token(request: Request) -> str | None:
    """Extract bearer token from request headers."""
    # Try X-API-Key header first
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key

    # Fall back to Authorization: Bearer <key>
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return None
