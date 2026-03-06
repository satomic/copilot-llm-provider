"""
Authentication endpoints for user login/registration.

Provides endpoints for the web UI authentication flow:
- GET /api/auth/status: Check if any users exist
- POST /api/auth/register: Create first user account
- POST /api/auth/login: Authenticate and get session token
- POST /api/auth/logout: Invalidate session token
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.backend.app.services.user_store import get_user_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class AuthCredentials(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class AuthStatusResponse(BaseModel):
    has_users: bool


class LoginResponse(BaseModel):
    token: str
    username: str


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    """Check whether any user accounts exist (public endpoint)."""
    store = get_user_store()
    return AuthStatusResponse(has_users=store.has_users())


@router.post("/register", response_model=LoginResponse)
async def register(body: AuthCredentials):
    """Register a new user account.

    Only allowed when no users exist yet (first-time setup).
    After registration, automatically logs in and returns a session token.
    """
    store = get_user_store()
    if store.has_users():
        raise HTTPException(
            status_code=403,
            detail="Registration is closed. Users already exist.",
        )

    if not store.register(body.username, body.password):
        raise HTTPException(status_code=409, detail="Username already taken")

    token = store.create_session(body.username)
    logger.info("User registered and logged in: %s", body.username)
    return LoginResponse(token=token, username=body.username)


@router.post("/login", response_model=LoginResponse)
async def login(body: AuthCredentials):
    """Authenticate with username and password, returns a session token."""
    store = get_user_store()
    if not store.authenticate(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = store.create_session(body.username)
    logger.info("User logged in: %s", body.username)
    return LoginResponse(token=token, username=body.username)


@router.post("/logout")
async def logout(request: Request):
    """Invalidate the current session token."""
    token = _extract_token(request)
    if token:
        store = get_user_store()
        store.invalidate_session(token)
    return {"status": "ok"}


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None
