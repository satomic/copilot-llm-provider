"""
Admin endpoints for server configuration and API key management.

Provides endpoints for:
- Legacy API key set/remove (backward compat)
- Auth status check
- Managed API key CRUD (create, list, update, delete)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import AuthInfo, verify_api_key
from backend.app.core.runtime_config import get_runtime_config
from backend.app.services.api_key_store import get_api_key_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ============================================================================
# Legacy auth status
# ============================================================================


class AuthStatusResponse(BaseModel):
    auth_enabled: bool
    api_key_preview: str | None = None


@router.get("/auth-status", response_model=AuthStatusResponse)
async def get_auth_status():
    """Check whether API key authentication is enabled (always public)."""
    config = get_runtime_config()
    key = config.api_key
    key_store = get_api_key_store()

    enabled = bool(key) or key_store.has_keys()
    preview = None
    if key and len(key) > 4:
        preview = f"{key[:4]}{'*' * (len(key) - 4)}"
    elif key:
        preview = "*" * len(key)
    return AuthStatusResponse(auth_enabled=enabled, api_key_preview=preview)


# ============================================================================
# Managed API keys
# ============================================================================


class CreateApiKeyRequest(BaseModel):
    alias: str = Field(..., min_length=1, max_length=100)
    allowed_models: list[str] | None = None
    max_requests: int | None = None
    max_premium_requests: int | None = None


@router.post("/api-keys")
async def create_api_key(
    body: CreateApiKeyRequest,
    auth: AuthInfo = Depends(verify_api_key),
):
    """Create a new managed API key. Requires admin (session) auth."""
    if auth.auth_type not in ("session", "legacy", "none"):
        raise HTTPException(status_code=403, detail="Admin access required")

    store = get_api_key_store()
    key = store.create_key(
        alias=body.alias,
        allowed_models=body.allowed_models,
        max_requests=body.max_requests,
        max_premium_requests=body.max_premium_requests,
    )
    return {"key": key, "alias": body.alias}


@router.get("/api-keys")
async def list_api_keys(auth: AuthInfo = Depends(verify_api_key)):
    """List all managed API keys."""
    if auth.auth_type not in ("session", "legacy", "none"):
        raise HTTPException(status_code=403, detail="Admin access required")

    store = get_api_key_store()
    return {"keys": store.list_keys()}


@router.put("/api-keys/{key:path}")
async def update_api_key(
    key: str,
    body: dict,
    auth: AuthInfo = Depends(verify_api_key),
):
    """Update a managed API key's settings."""
    if auth.auth_type not in ("session", "legacy", "none"):
        raise HTTPException(status_code=403, detail="Admin access required")

    store = get_api_key_store()
    kwargs: dict = {}
    if "alias" in body:
        kwargs["alias"] = body["alias"]
    if "allowed_models" in body:
        kwargs["allowed_models"] = body["allowed_models"]
    if "max_requests" in body:
        kwargs["max_requests"] = body["max_requests"]
    if "max_premium_requests" in body:
        kwargs["max_premium_requests"] = body["max_premium_requests"]
    if "enabled" in body:
        kwargs["enabled"] = body["enabled"]

    if not store.update_key(key, **kwargs):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "ok"}


@router.delete("/api-keys/{key:path}")
async def delete_api_key(
    key: str,
    auth: AuthInfo = Depends(verify_api_key),
):
    """Delete a managed API key."""
    if auth.auth_type not in ("session", "legacy", "none"):
        raise HTTPException(status_code=403, detail="Admin access required")

    store = get_api_key_store()
    if not store.delete_key(key):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "ok"}


@router.post("/api-keys/{key:path}/reset-usage")
async def reset_api_key_usage(
    key: str,
    auth: AuthInfo = Depends(verify_api_key),
):
    """Reset usage counters for a managed API key."""
    if auth.auth_type not in ("session", "legacy", "none"):
        raise HTTPException(status_code=403, detail="Admin access required")

    store = get_api_key_store()
    if not store.reset_usage(key):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "ok"}


# ============================================================================
# Legacy API key management (backward compatibility)
# ============================================================================


class SetApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=1)


@router.post("/set-api-key")
async def set_api_key(body: SetApiKeyRequest, auth: AuthInfo = Depends(verify_api_key)):
    """Set the legacy server API key."""
    if auth.auth_type not in ("session", "legacy", "none"):
        raise HTTPException(status_code=403, detail="Admin access required")

    config = get_runtime_config()
    config.api_key = body.api_key
    logger.info("Legacy API key configured via admin endpoint")
    return {"status": "ok", "message": "API key configured"}


@router.delete("/api-key")
async def remove_api_key(auth: AuthInfo = Depends(verify_api_key)):
    """Remove the legacy API key (disable legacy authentication)."""
    if auth.auth_type not in ("session", "legacy", "none"):
        raise HTTPException(status_code=403, detail="Admin access required")

    config = get_runtime_config()
    config.api_key = None
    logger.info("Legacy API key removed via admin endpoint")
    return {"status": "ok", "message": "Legacy authentication disabled"}
