"""
Session audit endpoints.

Provides read-only access to recorded chat sessions and
a continue-session endpoint to resume conversations.
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.core.auth import AuthInfo, verify_api_key
from backend.app.core.dependencies import get_provider
from backend.app.providers.base import (
    ChatCompletionRequest as InternalRequest,
    ChatMessage,
    Provider,
)
from backend.app.services.session_store import SessionRecord, get_session_store
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.get("")
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    model: str | None = Query(default=None),
    api_key_alias: str | None = Query(default=None),
    github_token_alias: str | None = Query(default=None),
    _auth: AuthInfo = Depends(verify_api_key),
):
    """List recorded sessions with pagination and optional filters."""
    store = get_session_store()
    sessions = store.list_sessions(
        limit=limit, offset=offset, model=model,
        api_key_alias=api_key_alias, github_token_alias=github_token_alias,
    )
    total = store.get_total_count(
        model=model, api_key_alias=api_key_alias,
        github_token_alias=github_token_alias,
    )
    return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}


@router.get("/filter-options")
async def filter_options(
    _auth: AuthInfo = Depends(verify_api_key),
):
    """Return distinct models and API key aliases for session filtering."""
    store = get_session_store()
    return store.get_filter_options()


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    _auth: AuthInfo = Depends(verify_api_key),
):
    """Get a specific session by ID."""
    store = get_session_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    _auth: AuthInfo = Depends(verify_api_key),
):
    """Delete a single session by ID."""
    store = get_session_store()
    if not store.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": 1}


class BatchDeleteRequest(BaseModel):
    """Request body for batch session deletion."""

    ids: list[str] = Field(..., min_length=1, description="Session IDs to delete.")


@router.post("/batch-delete")
async def batch_delete_sessions(
    body: BatchDeleteRequest,
    _auth: AuthInfo = Depends(verify_api_key),
):
    """Delete multiple sessions at once."""
    store = get_session_store()
    deleted = store.delete_batch(body.ids)
    return {"deleted": deleted}


class ContinueSessionRequest(BaseModel):
    """Request body for continuing a session conversation."""

    message: str = Field(..., min_length=1, description="New user message to send.")


@router.post("/{session_id}/continue")
async def continue_session(
    session_id: str,
    body: ContinueSessionRequest,
    fastapi_request: Request,
    provider: Provider = Depends(get_provider),
    _auth: AuthInfo = Depends(verify_api_key),
):
    """Continue a conversation from an existing session.

    Loads the session's full message history (including all prior
    assistant turns stored in the messages array), appends the new
    user message, streams the reply, and updates the same session
    file in-place so context accumulates across multiple continues.
    """
    store = get_session_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # The messages array already contains the full accumulated history.
    # The latest assistant turn is stored in response_content (not yet
    # in the messages array), so we need to fold it in first.
    existing_messages: list[dict] = list(session.get("messages", []))
    prev_response = session.get("response_content", "")
    if prev_response:
        existing_messages.append({"role": "assistant", "content": prev_response})

    # Append the new user message
    existing_messages.append({"role": "user", "content": body.message})

    # Build internal request from the full history
    history = [ChatMessage(role=m["role"], content=m["content"]) for m in existing_messages]

    model = session.get("model", "gpt-4.1")
    start_time = time.time()
    client_ip = fastapi_request.client.host if fastapi_request.client else None

    internal_request = InternalRequest(
        messages=history,
        model=model,
        stream=True,
        temperature=0.7,
        max_tokens=4096,
    )

    async def stream_generator():
        collected: list[str] = []
        try:
            async for delta in provider.chat_completion_stream(internal_request):
                if delta.delta_content is not None and delta.delta_content != "":
                    collected.append(delta.delta_content)
                    yield f"data: {delta.delta_content}\n\n"

            yield "data: [DONE]\n\n"

            # Update the SAME session file in-place with accumulated history.
            # messages = all prior messages including the new user turn
            # response_content = only the latest assistant reply
            duration_ms = (time.time() - start_time) * 1000
            session["messages"] = existing_messages
            session["response_content"] = "".join(collected)
            session["duration_ms"] = round(duration_ms, 1)
            session["timestamp"] = time.time()
            if client_ip:
                session["client_ip"] = client_ip
            store.update(session_id, session)

        except Exception as exc:
            logger.exception("Error during continue-session streaming")
            yield f"event: error\ndata: {str(exc)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
