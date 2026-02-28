"""
Anthropic-compatible messages endpoint.

Implements POST /v1/messages following the Anthropic Messages API specification.
Supports both streaming (SSE) and non-streaming response modes.
Integrates session recording and usage tracking.
"""

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
from backend.app.services.session_store import SessionRecord, get_session_store
from backend.app.services.usage_tracker import get_usage_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_text_content(content) -> str:
    """Extract plain text from Anthropic message content."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if hasattr(block, "text") and block.text is not None:
            parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _extract_system_text(system: str | list | None) -> str | None:
    """Extract plain text from the system field (string or list of content blocks)."""
    if system is None:
        return None
    if isinstance(system, str):
        return system
    parts: list[str] = []
    for block in system:
        if isinstance(block, dict) and block.get("text"):
            parts.append(block["text"])
    return "\n".join(parts) if parts else None


def _convert_anthropic_to_internal(request: MessagesRequest) -> InternalRequest:
    """Convert an Anthropic-format request to the internal provider format."""
    messages: list[ChatMessage] = []
    system_text = _extract_system_text(request.system)
    if system_text:
        messages.append(ChatMessage(role="system", content=system_text))
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
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "stop_sequence": "stop_sequence",
    }
    return mapping.get(internal_reason, "end_turn")


def _make_msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:24]}"


def _make_anthropic_error(
    status_code: int, message: str, error_type: str = "api_error"
) -> JSONResponse:
    error_resp = AnthropicErrorResponse(
        error=AnthropicErrorDetail(type=error_type, message=message)
    )
    return JSONResponse(status_code=status_code, content=error_resp.model_dump())


def _messages_to_dicts(request: MessagesRequest) -> list[dict]:
    """Convert Anthropic messages to dicts for session recording."""
    result = []
    system_text = _extract_system_text(request.system)
    if system_text:
        result.append({"role": "system", "content": system_text})
    for msg in request.messages:
        result.append({"role": msg.role, "content": _extract_text_content(msg.content)})
    return result


@router.post(
    "/v1/messages",
    response_model=None,
    summary="Create a message",
    description="Send a structured list of input messages and receive a model-generated "
    "response. Compatible with the Anthropic Messages API.",
)
async def create_message(
    request: MessagesRequest,
    fastapi_request: Request,
    provider: Provider = Depends(get_provider),
    auth: AuthInfo = Depends(verify_api_key),
):
    logger.info(
        "Anthropic messages request: model=%s stream=%s messages=%d",
        request.model,
        request.stream,
        len(request.messages),
    )

    start_time = time.time()
    client_ip = fastapi_request.client.host if fastapi_request.client else None

    # Check model permissions and usage limits for managed API keys
    check_model_permission(auth, request.model)
    is_premium = await provider.is_model_premium(request.model)
    check_usage_limits(auth, is_premium)

    # Track usage
    multiplier = await provider.get_model_multiplier(request.model)
    get_usage_tracker().record_request(
        model=request.model, api_format="anthropic", stream=request.stream,
        is_premium=is_premium, multiplier=multiplier,
        api_key_alias=auth.key_alias,
    )
    record_api_key_usage(auth, is_premium)

    try:
        internal_request = _convert_anthropic_to_internal(request)
    except Exception as exc:
        logger.warning("Failed to convert Anthropic request: %s", exc)
        return _make_anthropic_error(400, str(exc), "invalid_request_error")

    if not request.stream:
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

            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                response_content=internal_response.content,
                stream=False,
                duration_ms=round(duration_ms, 1),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
            )
            get_session_store().save(record)

            return response

        except ValueError as exc:
            logger.warning("Invalid request: %s", exc)
            return _make_anthropic_error(400, str(exc), "invalid_request_error")
        except Exception as exc:
            logger.exception("Provider error during Anthropic message")
            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                stream=False,
                duration_ms=round(duration_ms, 1),
                status="error",
                error_message=str(exc),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
            )
            get_session_store().save(record)
            return _make_anthropic_error(500, str(exc), "api_error")

    # --- Streaming path ---
    async def anthropic_stream_generator():
        msg_id = _make_msg_id()
        output_tokens = 0
        collected_content = []

        try:
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

            block_start = ContentBlockStartEvent(
                index=0, content_block=TextBlock(text="")
            )
            yield f"event: content_block_start\ndata: {block_start.model_dump_json()}\n\n"

            ping = PingEvent()
            yield f"event: ping\ndata: {ping.model_dump_json()}\n\n"

            finish_reason = "end_turn"
            async for delta in provider.chat_completion_stream(internal_request):
                if delta.delta_content is not None and delta.delta_content != "":
                    output_tokens += 1
                    collected_content.append(delta.delta_content)
                    block_delta = ContentBlockDeltaEvent(
                        index=0, delta=TextDelta(text=delta.delta_content)
                    )
                    yield f"event: content_block_delta\ndata: {block_delta.model_dump_json()}\n\n"
                if delta.finish_reason:
                    finish_reason = _map_finish_reason(delta.finish_reason)

            block_stop = ContentBlockStopEvent(index=0)
            yield f"event: content_block_stop\ndata: {block_stop.model_dump_json()}\n\n"

            msg_delta = MessageDeltaEvent(
                delta=MessageDeltaPayload(stop_reason=finish_reason),
                usage=MessageDeltaUsage(output_tokens=output_tokens),
            )
            yield f"event: message_delta\ndata: {msg_delta.model_dump_json()}\n\n"

            msg_stop = MessageStopEvent()
            yield f"event: message_stop\ndata: {msg_stop.model_dump_json()}\n\n"

            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                response_content="".join(collected_content),
                stream=True,
                duration_ms=round(duration_ms, 1),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
            )
            get_session_store().save(record)

        except Exception as exc:
            logger.exception("Error during Anthropic streaming")
            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                response_content="".join(collected_content),
                stream=True,
                duration_ms=round(duration_ms, 1),
                status="error",
                error_message=str(exc),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
            )
            get_session_store().save(record)
            error_data = AnthropicErrorResponse(
                error=AnthropicErrorDetail(type="api_error", message=str(exc))
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
