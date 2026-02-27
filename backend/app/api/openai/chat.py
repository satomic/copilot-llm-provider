"""
OpenAI-compatible chat completions endpoint.

Implements POST /v1/chat/completions following the OpenAI API specification.
Supports both streaming (SSE) and non-streaming response modes.

Wire format conversion:
    OpenAI ChatCompletionRequest -> internal ChatCompletionRequest -> Provider
    Provider response -> internal ChatCompletionResponse -> OpenAI ChatCompletionResponse
"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from backend.app.core.auth import verify_api_key
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

logger = logging.getLogger(__name__)

router = APIRouter()


def _convert_openai_to_internal(
    request: OpenAIChatCompletionRequest,
) -> InternalRequest:
    """Convert an OpenAI-format request to the internal provider format.

    Handles the stop field which can be a string or list of strings in OpenAI
    format but is always a list of strings (or None) internally.
    """
    messages = [
        ChatMessage(role=msg.role, content=msg.content)
        for msg in request.messages
    ]

    # Normalize stop: OpenAI accepts str | list[str] | None
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
    provider: Provider = Depends(get_provider),
    _api_key: str | None = Depends(verify_api_key),
):
    """Handle an OpenAI-format chat completion request.

    Converts the OpenAI request format to the internal format, delegates
    to the provider, and converts the response back.

    For streaming requests, returns a StreamingResponse with SSE events
    in the OpenAI chunk format, terminated by a "data: [DONE]" event.

    Args:
        request: The OpenAI-format chat completion request.
        provider: The LLM provider (injected).
        _api_key: Verified API key (injected, unused directly).

    Returns:
        OpenAI-format chat completion response (or StreamingResponse for SSE).
    """
    logger.info(
        "OpenAI chat completion request: model=%s stream=%s messages=%d",
        request.model,
        request.stream,
        len(request.messages),
    )

    try:
        internal_request = _convert_openai_to_internal(request)
    except Exception as exc:
        logger.warning("Failed to convert OpenAI request: %s", exc)
        return _make_openai_error(400, str(exc), "invalid_request_error")

    if not request.stream:
        # --- Non-streaming path ---
        try:
            internal_response = await provider.chat_completion(internal_request)
            openai_response = _convert_internal_to_openai(internal_response)
            logger.debug(
                "Chat completion completed: id=%s tokens=%d",
                openai_response.id,
                openai_response.usage.total_tokens,
            )
            return openai_response
        except ValueError as exc:
            logger.warning("Invalid request: %s", exc)
            return _make_openai_error(400, str(exc), "invalid_request_error")
        except Exception as exc:
            logger.exception("Provider error during chat completion")
            return _make_openai_error(500, str(exc), "server_error")

    # --- Streaming path ---
    async def openai_stream_generator():
        """Async generator that yields SSE-formatted OpenAI streaming chunks."""
        created = int(time.time())
        stream_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        first_chunk = True

        try:
            async for delta in provider.chat_completion_stream(internal_request):
                if first_chunk:
                    # First chunk: include role="assistant" with initial content
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
                    first_chunk = False
                    # If this first delta also had content, we already included it above.
                    # If delta_content was None and finish_reason is set, handle below.
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
                    # Final chunk: signal finish_reason with empty delta
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
                    # Content chunk
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

        except Exception as exc:
            logger.exception("Error during OpenAI streaming")
            error_data = {
                "error": {
                    "message": str(exc),
                    "type": "server_error",
                    "code": "500",
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        # Always terminate with [DONE]
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
