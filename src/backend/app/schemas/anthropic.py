"""
Pydantic models for the Anthropic Messages API wire format.

These models define the exact request and response shapes for Anthropic-compatible
endpoints. They must match the real Anthropic API specification so that existing
Anthropic client libraries (anthropic-python, anthropic-node, etc.) work seamlessly.

Key differences from OpenAI:
- System message is a separate top-level field (not in the messages array).
- Response content uses typed content blocks (TextBlock) instead of a plain string.
- Streaming uses named event types with typed data payloads.

Reference: https://docs.anthropic.com/en/docs/api/messages
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Shared Sub-Models
# =============================================================================


class AnthropicUsage(BaseModel):
    """Token usage statistics for an Anthropic response."""

    input_tokens: int = 0
    output_tokens: int = 0


# =============================================================================
# Content Blocks
# =============================================================================


class TextBlock(BaseModel):
    """A text content block in a message.

    Anthropic uses typed content blocks to support multiple content types
    (text, tool_use, tool_result, images). We only support text for now.
    """

    type: Literal["text"] = "text"
    text: str = Field(..., description="The text content.")


class ContentBlockParam(BaseModel):
    """A content block in a message (used in requests).

    The Anthropic API allows message content to be either a plain string
    or a list of typed content blocks. This model represents one block.
    Supports text, image, tool_use, and tool_result types.
    """

    model_config = {"extra": "allow"}

    type: str = "text"
    text: str | None = Field(default=None, description="Text content (for type='text').")


class MessageContent(BaseModel):
    """A single message in the conversation.

    Unlike OpenAI, messages in the Anthropic format do NOT include system
    messages. The system prompt is a separate top-level field.

    Content can be a plain string or a list of content blocks, matching
    the Anthropic API specification. Supports text, tool_use, and tool_result.
    """

    role: Literal["user", "assistant"] = Field(
        ..., description="The role of the message author. No 'system' role here."
    )
    content: str | list[Any] = Field(
        ..., description="The text content of the message, or a list of content blocks."
    )


# =============================================================================
# Messages Request
# =============================================================================


class MessageMetadata(BaseModel):
    """Optional metadata for a messages request."""

    user_id: str | None = Field(
        default=None,
        description="An external identifier for the user making the request.",
    )


class MessagesRequest(BaseModel):
    """Anthropic Messages API request body.

    Reference: https://docs.anthropic.com/en/docs/api/messages
    """

    model: str = Field(
        ..., description="The model to use (e.g., 'claude-sonnet-4-20250514')."
    )
    messages: list[MessageContent] = Field(
        ..., description="Input messages. System messages go in the 'system' field."
    )
    max_tokens: int = Field(
        ..., gt=0, description="Maximum number of tokens to generate. Required."
    )
    system: str | list[Any] | None = Field(
        default=None,
        description="System prompt. Can be a plain string or a list of content blocks "
        "(e.g., [{\"type\": \"text\", \"text\": \"...\", \"cache_control\": {...}}]).",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response using SSE.",
    )
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling temperature between 0 and 1.",
    )
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter.",
    )
    stop_sequences: list[str] | None = Field(
        default=None,
        description="Custom sequences that will cause the model to stop generating.",
    )
    tools: list[dict[str, Any]] | None = Field(
        default=None,
        description="Definitions of tools the model may use.",
    )
    metadata: MessageMetadata | None = Field(
        default=None,
        description="Optional metadata about the request.",
    )


# =============================================================================
# Messages Response (Non-Streaming)
# =============================================================================


class MessagesResponse(BaseModel):
    """Anthropic Messages API response body.

    Reference: https://docs.anthropic.com/en/docs/api/messages
    """

    id: str = Field(..., description="Unique message identifier (msg_xxx format).")
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: list[Any] = Field(
        ..., description="The generated content blocks (text, tool_use, etc.)."
    )
    model: str = Field(..., description="The model that generated this response.")
    stop_reason: Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"] | None = Field(
        default="end_turn",
        description="The reason the model stopped generating.",
    )
    stop_sequence: str | None = Field(
        default=None,
        description="The stop sequence that caused generation to stop, if applicable.",
    )
    usage: AnthropicUsage = Field(
        default_factory=AnthropicUsage,
        description="Token usage statistics.",
    )


# =============================================================================
# Streaming Event Types
# =============================================================================


class MessageStartEvent(BaseModel):
    """Sent once at the start of a streaming response.

    Contains the initial message object with metadata but no content yet.
    """

    type: Literal["message_start"] = "message_start"
    message: MessagesResponse


class ContentBlockStartEvent(BaseModel):
    """Sent at the start of each content block."""

    type: Literal["content_block_start"] = "content_block_start"
    index: int = Field(..., description="Index of the content block.")
    content_block: dict[str, Any] = Field(
        ..., description="The content block (text or tool_use)."
    )


class TextDelta(BaseModel):
    """Delta payload for text content."""

    type: Literal["text_delta"] = "text_delta"
    text: str = Field(..., description="Incremental text content.")


class ContentBlockDeltaEvent(BaseModel):
    """Sent for each incremental update to a content block.

    This is the primary streaming event that contains new text or tool input JSON.
    """

    type: Literal["content_block_delta"] = "content_block_delta"
    index: int = Field(..., description="Index of the content block being updated.")
    delta: dict[str, Any] = Field(
        ..., description="The delta payload (text_delta or input_json_delta)."
    )


class ContentBlockStopEvent(BaseModel):
    """Sent when a content block is complete."""

    type: Literal["content_block_stop"] = "content_block_stop"
    index: int = Field(..., description="Index of the completed content block.")


class MessageDeltaUsage(BaseModel):
    """Usage information sent with the message_delta event."""

    output_tokens: int = 0


class MessageDeltaPayload(BaseModel):
    """Delta payload for the message_delta event."""

    stop_reason: Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"] | None = None
    stop_sequence: str | None = None


class MessageDeltaEvent(BaseModel):
    """Sent near the end of the stream with final message metadata."""

    type: Literal["message_delta"] = "message_delta"
    delta: MessageDeltaPayload
    usage: MessageDeltaUsage = Field(default_factory=MessageDeltaUsage)


class MessageStopEvent(BaseModel):
    """Sent as the final event in a streaming response."""

    type: Literal["message_stop"] = "message_stop"


class PingEvent(BaseModel):
    """Keep-alive ping event sent periodically during streaming."""

    type: Literal["ping"] = "ping"


# =============================================================================
# Error Response
# =============================================================================


class AnthropicErrorDetail(BaseModel):
    """Anthropic error detail object."""

    type: str = Field(..., description="Error type identifier.")
    message: str = Field(..., description="Human-readable error message.")


class AnthropicErrorResponse(BaseModel):
    """Anthropic error response wrapper.

    Anthropic error format:
    {"type": "error", "error": {"type": "...", "message": "..."}}
    """

    type: Literal["error"] = "error"
    error: AnthropicErrorDetail
