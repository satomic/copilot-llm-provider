"""
Anthropic-compatible messages endpoint.

Implements POST /v1/messages following the Anthropic Messages API specification.
Supports both streaming (SSE) and non-streaming response modes.

Key differences from OpenAI format:
- System message is a top-level field, not part of the messages array.
- Streaming uses named event types (message_start, content_block_delta, etc.)
  instead of a single "data:" stream with a [DONE] terminator.
- Response uses content blocks instead of a single content string.

Wire format conversion:
    Anthropic MessagesRequest -> internal ChatCompletionRequest -> Provider
    Provider response -> internal ChatCompletionResponse -> Anthropic MessagesResponse
"""

import logging
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from backend.app.core.auth import verify_api_key
from backend.app.core.dependencies import get_provider
from backend.app.providers.base import (
    ChatCompletionRequest as InternalRequest,
    ChatMessage,
    Provider,
)
from backend.app.schemas.anthropic import (
    AnthropicErrorDetail,
    AnthropicErrorResponse,
    AnthropicUsage,
    ContentBlockDeltaEvent,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    MessageDeltaEvent,
    MessageDeltaPayload,
    MessageDeltaUsage,
    MessageStartEvent,
    MessageStopEvent,
    MessagesRequest,
    MessagesResponse,
    PingEvent,
    TextBlock,
    TextDelta,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_text_content(content) -> str:
    """Extract plain text from Anthropic message content.

    Anthropic message content can be either a plain string or a list of
    typed content blocks. This function normalizes both forms to a string.

    Args:
        content: Either a string or a list of content block dicts/objects.

    Returns:
        The concatenated text content.
    """
    if isinstance(content, str):
        return content

    # content is a list of content blocks
    parts: list[str] = []
    for block in content:
        if hasattr(block, "text") and block.text is not None:
            parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _convert_anthropic_to_internal(request: MessagesRequest) -> InternalRequest:
    """Convert an Anthropic-format request to the internal provider format.

    Handles the system message extraction from the top-level field and
    content block normalization.
    """
    messages: list[ChatMessage] = []

    # Anthropic puts system prompt as a top-level field, not in messages.
    # Convert it to an internal system ChatMessage at the start.
    if request.system:
        messages.append(ChatMessage(role="system", content=request.system))

    # Convert each Anthropic message to internal format
    for msg in request.messages:
        text_content = _extract_text_content(msg.content)
        messages.append(ChatMessage(role=msg.role, content=text_content))

    return InternalRequest(
        messages=messages,
        model=request.model,
        stream=request.stream,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        stop=request.stop_sequences,
    )


def _map_finish_reason(internal_reason: str) -> str:
    """Map internal finish reasons to Anthropic stop_reason values.

    Internal: "stop", "length", "error"
    Anthropic: "end_turn", "max_tokens", "stop_sequence"
    """
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "stop_sequence": "stop_sequence",
    }
    return mapping.get(internal_reason, "end_turn")


def _make_msg_id() -> str:
    """Generate a unique Anthropic message ID in msg_xxx format."""
    return f"msg_{uuid.uuid4().hex[:24]}"


def _make_anthropic_error(
    status_code: int, message: str, error_type: str = "api_error"
) -> JSONResponse:
    """Build an Anthropic-style error JSON response."""
    error_resp = AnthropicErrorResponse(
        error=AnthropicErrorDetail(
            type=error_type,
            message=message,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=error_resp.model_dump(),
    )


@router.post(
    "/v1/messages",
    response_model=None,
    summary="Create a message",
    description="Send a structured list of input messages and receive a model-generated "
    "response. Compatible with the Anthropic Messages API.",
)
async def create_message(
    request: MessagesRequest,
    provider: Provider = Depends(get_provider),
    _api_key: str | None = Depends(verify_api_key),
):
    """Handle an Anthropic-format messages request.

    Converts the Anthropic request format to the internal format (including
    extracting the system message from the top-level field), delegates to
    the provider, and converts the response back to Anthropic format.

    For streaming requests, returns a StreamingResponse with SSE events
    using Anthropic event types: message_start, content_block_start,
    content_block_delta, content_block_stop, message_delta, message_stop.

    Args:
        request: The Anthropic-format messages request.
        provider: The LLM provider (injected).
        _api_key: Verified API key (injected, unused directly).

    Returns:
        Anthropic-format messages response (or StreamingResponse for SSE).
    """
    logger.info(
        "Anthropic messages request: model=%s stream=%s messages=%d",
        request.model,
        request.stream,
        len(request.messages),
    )

    try:
        internal_request = _convert_anthropic_to_internal(request)
    except Exception as exc:
        logger.warning("Failed to convert Anthropic request: %s", exc)
        return _make_anthropic_error(400, str(exc), "invalid_request_error")

    if not request.stream:
        # --- Non-streaming path ---
        try:
            internal_response = await provider.chat_completion(internal_request)

            stop_reason = _map_finish_reason(internal_response.finish_reason)
            response = MessagesResponse(
                id=_make_msg_id(),
                content=[TextBlock(text=internal_response.content)],
                model=internal_response.model,
                stop_reason=stop_reason,
                usage=AnthropicUsage(
                    input_tokens=internal_response.usage.prompt_tokens,
                    output_tokens=internal_response.usage.completion_tokens,
                ),
            )
            logger.debug(
                "Anthropic message completed: id=%s output_tokens=%d",
                response.id,
                response.usage.output_tokens,
            )
            return response

        except ValueError as exc:
            logger.warning("Invalid request: %s", exc)
            return _make_anthropic_error(400, str(exc), "invalid_request_error")
        except Exception as exc:
            logger.exception("Provider error during Anthropic message")
            return _make_anthropic_error(500, str(exc), "api_error")

    # --- Streaming path ---
    async def anthropic_stream_generator():
        """Async generator that yields SSE-formatted Anthropic streaming events.

        Anthropic SSE format requires both an 'event: <type>' line and a
        'data: {json}' line for each event, unlike OpenAI which only uses 'data:'.

        Event sequence:
        1. message_start - initial message metadata
        2. content_block_start - start of each content block
        3. ping - keep-alive
        4. content_block_delta - incremental text (repeated)
        5. content_block_stop - end of content block
        6. message_delta - final message metadata (stop_reason, usage)
        7. message_stop - stream terminator
        """
        msg_id = _make_msg_id()
        output_tokens = 0

        try:
            # 1. message_start event
            message_start = MessageStartEvent(
                message=MessagesResponse(
                    id=msg_id,
                    content=[],
                    model=request.model,
                    stop_reason=None,
                    usage=AnthropicUsage(input_tokens=0, output_tokens=0),
                )
            )
            yield f"event: message_start\ndata: {message_start.model_dump_json()}\n\n"

            # 2. content_block_start event
            block_start = ContentBlockStartEvent(
                index=0,
                content_block=TextBlock(text=""),
            )
            yield f"event: content_block_start\ndata: {block_start.model_dump_json()}\n\n"

            # 3. ping event
            ping = PingEvent()
            yield f"event: ping\ndata: {ping.model_dump_json()}\n\n"

            # 4. Stream content deltas from provider
            finish_reason = "end_turn"
            async for delta in provider.chat_completion_stream(internal_request):
                if delta.delta_content is not None and delta.delta_content != "":
                    output_tokens += 1  # Approximate: count deltas as token proxy
                    block_delta = ContentBlockDeltaEvent(
                        index=0,
                        delta=TextDelta(text=delta.delta_content),
                    )
                    yield f"event: content_block_delta\ndata: {block_delta.model_dump_json()}\n\n"

                if delta.finish_reason:
                    finish_reason = _map_finish_reason(delta.finish_reason)

            # 5. content_block_stop event
            block_stop = ContentBlockStopEvent(index=0)
            yield f"event: content_block_stop\ndata: {block_stop.model_dump_json()}\n\n"

            # 6. message_delta event
            msg_delta = MessageDeltaEvent(
                delta=MessageDeltaPayload(stop_reason=finish_reason),
                usage=MessageDeltaUsage(output_tokens=output_tokens),
            )
            yield f"event: message_delta\ndata: {msg_delta.model_dump_json()}\n\n"

            # 7. message_stop event
            msg_stop = MessageStopEvent()
            yield f"event: message_stop\ndata: {msg_stop.model_dump_json()}\n\n"

        except Exception as exc:
            logger.exception("Error during Anthropic streaming")
            error_data = AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="api_error",
                    message=str(exc),
                )
            )
            yield f"event: error\ndata: {error_data.model_dump_json()}\n\n"

    return StreamingResponse(
        anthropic_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
