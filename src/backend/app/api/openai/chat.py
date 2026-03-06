"""
OpenAI-compatible chat completions endpoint.

Implements POST /v1/chat/completions following the OpenAI API specification.
Supports both streaming (SSE) and non-streaming response modes.
Integrates session recording and usage tracking.
"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.app.core.auth import (
    AuthInfo,
    check_model_permission,
    check_usage_limits,
    record_api_key_usage,
    verify_api_key,
)
from backend.app.core.dependencies import get_provider
from backend.app.providers.base import (
    ChatCompletionRequest as InternalRequest,
    ChatCompletionResponse as InternalResponse,
    ChatMessage,
    Provider,
)
from backend.app.schemas.openai import (
    ChatCompletionChunk,
    ChatCompletionRequest as OpenAIChatCompletionRequest,
    ChatCompletionResponse as OpenAIChatCompletionResponse,
    Choice,
    ChoiceMessage,
    ChunkChoice,
    DeltaContent,
    ErrorDetail,
    ErrorResponse,
    Usage,
)
from backend.app.services.session_store import SessionRecord, get_session_store
from backend.app.services.usage_tracker import get_usage_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


def _convert_openai_to_internal(
    request: OpenAIChatCompletionRequest,
) -> InternalRequest:
    """Convert an OpenAI-format request to the internal provider format."""
    messages = [
        ChatMessage(role=msg.role, content=msg.content)
        for msg in request.messages
    ]

    stop: list[str] | None = None
    if isinstance(request.stop, str):
        stop = [request.stop]
    elif isinstance(request.stop, list):
        stop = request.stop

    return InternalRequest(
        messages=messages,
        model=request.model,
        stream=request.stream,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        stop=stop,
    )


def _convert_internal_to_openai(
    response: InternalResponse,
) -> OpenAIChatCompletionResponse:
    """Convert an internal provider response to OpenAI wire format."""
    return OpenAIChatCompletionResponse(
        id=response.id,
        model=response.model,
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(content=response.content),
                finish_reason=response.finish_reason,
            )
        ],
        usage=Usage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        ),
    )


def _make_openai_error(
    status_code: int, message: str, error_type: str = "api_error"
) -> JSONResponse:
    """Build an OpenAI-style error JSON response."""
    error_resp = ErrorResponse(
        error=ErrorDetail(
            message=message,
            type=error_type,
            code=str(status_code),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=error_resp.model_dump(),
    )


@router.post(
    "/v1/chat/completions",
    response_model=None,
    summary="Create a chat completion",
    description="Generates a model response for the given chat conversation. "
    "Compatible with the OpenAI Chat Completions API.",
)
async def create_chat_completion(
    request: OpenAIChatCompletionRequest,
    fastapi_request: Request,
    provider: Provider = Depends(get_provider),
    auth: AuthInfo = Depends(verify_api_key),
):
    logger.info(
        "OpenAI chat completion request: model=%s stream=%s messages=%d",
        request.model,
        request.stream,
        len(request.messages),
    )

    start_time = time.time()
    client_ip = fastapi_request.client.host if fastapi_request.client else None

    # Capture GitHub token info from the provider selection
    github_token_id = getattr(fastapi_request.state, "github_token_id", None)
    github_token_alias = getattr(fastapi_request.state, "github_token_alias", None)

    # Check model permissions and usage limits for managed API keys
    check_model_permission(auth, request.model)
    is_premium = await provider.is_model_premium(request.model)
    check_usage_limits(auth, is_premium)

    # Track usage
    multiplier = await provider.get_model_multiplier(request.model)
    get_usage_tracker().record_request(
        model=request.model, api_format="openai", stream=request.stream,
        is_premium=is_premium, multiplier=multiplier,
        api_key_alias=auth.key_alias,
        github_token_alias=github_token_alias,
    )
    record_api_key_usage(auth, is_premium)

    # Track premium request on the token pool
    if is_premium and github_token_id:
        from backend.app.services.token_pool import get_token_pool
        get_token_pool().record_premium_request(github_token_id)

    try:
        internal_request = _convert_openai_to_internal(request)
    except Exception as exc:
        logger.warning("Failed to convert OpenAI request: %s", exc)
        return _make_openai_error(400, str(exc), "invalid_request_error")

    if not request.stream:
        try:
            internal_response = await provider.chat_completion(internal_request)
            openai_response = _convert_internal_to_openai(internal_response)

            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="openai",
                messages=[m.model_dump() for m in request.messages],
                response_content=internal_response.content,
                stream=False,
                duration_ms=round(duration_ms, 1),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)

            return openai_response
        except ValueError as exc:
            logger.warning("Invalid request: %s", exc)
            return _make_openai_error(400, str(exc), "invalid_request_error")
        except Exception as exc:
            logger.exception("Provider error during chat completion")
            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="openai",
                messages=[m.model_dump() for m in request.messages],
                stream=False,
                duration_ms=round(duration_ms, 1),
                status="error",
                error_message=str(exc),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)
            return _make_openai_error(500, str(exc), "server_error")

    # --- Streaming path ---
    async def openai_stream_generator():
        created = int(time.time())
        stream_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        first_chunk = True
        collected_content = []

        try:
            async for delta in provider.chat_completion_stream(internal_request):
                if first_chunk:
                    chunk = ChatCompletionChunk(
                        id=delta.id or stream_id,
                        created=created,
                        model=delta.model or request.model,
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=DeltaContent(
                                    role="assistant",
                                    content=delta.delta_content or "",
                                ),
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    if delta.delta_content:
                        collected_content.append(delta.delta_content)
                    first_chunk = False
                    if delta.finish_reason:
                        final_chunk = ChatCompletionChunk(
                            id=delta.id or stream_id,
                            created=created,
                            model=delta.model or request.model,
                            choices=[
                                ChunkChoice(
                                    index=0,
                                    delta=DeltaContent(),
                                    finish_reason=delta.finish_reason,
                                )
                            ],
                        )
                        yield f"data: {final_chunk.model_dump_json()}\n\n"
                elif delta.finish_reason:
                    chunk = ChatCompletionChunk(
                        id=delta.id or stream_id,
                        created=created,
                        model=delta.model or request.model,
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=DeltaContent(),
                                finish_reason=delta.finish_reason,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                elif delta.delta_content is not None:
                    collected_content.append(delta.delta_content)
                    chunk = ChatCompletionChunk(
                        id=delta.id or stream_id,
                        created=created,
                        model=delta.model or request.model,
                        choices=[
                            ChunkChoice(
                                index=0,
                                delta=DeltaContent(content=delta.delta_content),
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="openai",
                messages=[m.model_dump() for m in request.messages],
                response_content="".join(collected_content),
                stream=True,
                duration_ms=round(duration_ms, 1),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)

        except Exception as exc:
            logger.exception("Error during OpenAI streaming")
            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="openai",
                messages=[m.model_dump() for m in request.messages],
                response_content="".join(collected_content),
                stream=True,
                duration_ms=round(duration_ms, 1),
                status="error",
                error_message=str(exc),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)
            error_data = {
                "error": {
                    "message": str(exc),
                    "type": "server_error",
                    "code": "500",
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        openai_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
