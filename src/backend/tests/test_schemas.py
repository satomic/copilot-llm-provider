"""
Tests for Pydantic schema validation and serialization.

Verifies that request/response schemas validate correctly, enforce
required fields, apply defaults, and round-trip through JSON serialization.
"""

import pytest
from pydantic import ValidationError

from src.backend.app.schemas.openai import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageContent,
    Choice,
    ChoiceMessage,
    ChunkChoice,
    DeltaContent,
    ErrorDetail,
    ErrorResponse,
    ModelList,
    ModelObject,
    Usage,
)
from src.backend.app.schemas.anthropic import (
    AnthropicErrorDetail,
    AnthropicErrorResponse,
    AnthropicUsage,
    ContentBlockDeltaEvent,
    ContentBlockParam,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    MessageContent,
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


# =============================================================================
# OpenAI Schema Tests
# =============================================================================


class TestOpenAIChatCompletionRequest:
    """Tests for the OpenAI ChatCompletionRequest schema."""

    def test_valid_minimal_request(self) -> None:
        """A request with just model and messages should validate."""
        req = ChatCompletionRequest(
            model="gpt-4.1",
            messages=[
                ChatMessageContent(role="user", content="Hello"),
            ],
        )
        assert req.model == "gpt-4.1"
        assert len(req.messages) == 1
        assert req.messages[0].role == "user"

    def test_defaults_are_applied(self) -> None:
        """Default values for optional fields should be set."""
        req = ChatCompletionRequest(
            model="gpt-4.1",
            messages=[ChatMessageContent(role="user", content="Hi")],
        )
        assert req.stream is False
        assert req.temperature == 1.0
        assert req.max_tokens is None
        assert req.top_p is None
        assert req.stop is None
        assert req.frequency_penalty == 0.0
        assert req.presence_penalty == 0.0
        assert req.n == 1
        assert req.user is None

    def test_missing_model_raises_error(self) -> None:
        """Omitting the required 'model' field should raise ValidationError."""
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                messages=[ChatMessageContent(role="user", content="Hi")],
            )

    def test_missing_messages_raises_error(self) -> None:
        """Omitting the required 'messages' field should raise ValidationError."""
        with pytest.raises(ValidationError):
            ChatCompletionRequest(model="gpt-4.1")

    def test_temperature_out_of_range_raises_error(self) -> None:
        """Temperature outside [0, 2] should raise ValidationError."""
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                model="gpt-4.1",
                messages=[ChatMessageContent(role="user", content="Hi")],
                temperature=3.0,
            )

    def test_invalid_role_raises_error(self) -> None:
        """An invalid role in messages should raise ValidationError."""
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                model="gpt-4.1",
                messages=[
                    ChatMessageContent(role="invalid_role", content="Hi"),
                ],
            )

    def test_stop_accepts_string(self) -> None:
        """The stop field should accept a single string."""
        req = ChatCompletionRequest(
            model="gpt-4.1",
            messages=[ChatMessageContent(role="user", content="Hi")],
            stop="END",
        )
        assert req.stop == "END"

    def test_stop_accepts_list(self) -> None:
        """The stop field should accept a list of strings."""
        req = ChatCompletionRequest(
            model="gpt-4.1",
            messages=[ChatMessageContent(role="user", content="Hi")],
            stop=["END", "STOP"],
        )
        assert req.stop == ["END", "STOP"]

    def test_serialization_round_trip(self) -> None:
        """Serializing to dict and back should produce the same model."""
        original = ChatCompletionRequest(
            model="gpt-4.1",
            messages=[
                ChatMessageContent(role="system", content="Be helpful"),
                ChatMessageContent(role="user", content="Hello"),
            ],
            temperature=0.7,
            max_tokens=200,
            stream=True,
        )
        data = original.model_dump()
        restored = ChatCompletionRequest(**data)
        assert restored.model == original.model
        assert len(restored.messages) == len(original.messages)
        assert restored.temperature == original.temperature
        assert restored.max_tokens == original.max_tokens
        assert restored.stream == original.stream


class TestOpenAIChatCompletionResponse:
    """Tests for the OpenAI ChatCompletionResponse schema."""

    def test_valid_response(self) -> None:
        """A fully populated response should validate."""
        resp = ChatCompletionResponse(
            id="chatcmpl-abc123",
            model="gpt-4.1",
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(content="Hello there!"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )
        assert resp.object == "chat.completion"
        assert resp.choices[0].message.role == "assistant"

    def test_default_object_type(self) -> None:
        """The object field should default to 'chat.completion'."""
        resp = ChatCompletionResponse(
            id="chatcmpl-abc123",
            model="gpt-4.1",
            choices=[
                Choice(message=ChoiceMessage(content="Hi"))
            ],
        )
        assert resp.object == "chat.completion"

    def test_serialization_round_trip(self) -> None:
        """Response should round-trip through JSON serialization."""
        resp = ChatCompletionResponse(
            id="chatcmpl-abc123",
            model="gpt-4.1",
            choices=[Choice(message=ChoiceMessage(content="Hi"))],
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
        json_str = resp.model_dump_json()
        restored = ChatCompletionResponse.model_validate_json(json_str)
        assert restored.id == resp.id
        assert restored.model == resp.model
        assert restored.choices[0].message.content == "Hi"


class TestOpenAIChunkSchema:
    """Tests for streaming chunk schemas."""

    def test_chunk_schema(self) -> None:
        """A ChatCompletionChunk should validate correctly."""
        chunk = ChatCompletionChunk(
            id="chatcmpl-abc123",
            model="gpt-4.1",
            choices=[
                ChunkChoice(
                    delta=DeltaContent(role="assistant", content="Hello"),
                    finish_reason=None,
                )
            ],
        )
        assert chunk.object == "chat.completion.chunk"

    def test_delta_content_with_role_only(self) -> None:
        """A delta with only role set (first chunk pattern) should validate."""
        delta = DeltaContent(role="assistant")
        assert delta.role == "assistant"
        assert delta.content is None

    def test_delta_content_with_content_only(self) -> None:
        """A delta with only content (subsequent chunk) should validate."""
        delta = DeltaContent(content="hello")
        assert delta.role is None
        assert delta.content == "hello"


class TestOpenAIModelSchemas:
    """Tests for model listing schemas."""

    def test_model_object(self) -> None:
        """A ModelObject should have the correct defaults."""
        model = ModelObject(id="gpt-4.1", created=1234567890)
        assert model.object == "model"
        assert model.owned_by == "copilot"

    def test_model_list(self) -> None:
        """A ModelList should have object='list' and a data array."""
        model_list = ModelList(
            data=[
                ModelObject(id="gpt-4.1", created=1234567890),
                ModelObject(id="gpt-3.5", created=1234567890, owned_by="openai"),
            ]
        )
        assert model_list.object == "list"
        assert len(model_list.data) == 2


class TestOpenAIErrorSchema:
    """Tests for error response schemas."""

    def test_error_response(self) -> None:
        """An ErrorResponse should have the correct structure."""
        err = ErrorResponse(
            error=ErrorDetail(
                message="Something went wrong",
                type="server_error",
                code="500",
            )
        )
        assert err.error.message == "Something went wrong"
        assert err.error.type == "server_error"


# =============================================================================
# Anthropic Schema Tests
# =============================================================================


class TestAnthropicMessagesRequest:
    """Tests for the Anthropic MessagesRequest schema."""

    def test_valid_minimal_request(self) -> None:
        """A request with model, messages, and max_tokens should validate."""
        req = MessagesRequest(
            model="claude-sonnet-4",
            max_tokens=1024,
            messages=[
                MessageContent(role="user", content="Hello"),
            ],
        )
        assert req.model == "claude-sonnet-4"
        assert req.max_tokens == 1024

    def test_max_tokens_is_required(self) -> None:
        """Omitting max_tokens should raise ValidationError."""
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="claude-sonnet-4",
                messages=[MessageContent(role="user", content="Hello")],
            )

    def test_defaults_are_applied(self) -> None:
        """Default values for optional fields should be set."""
        req = MessagesRequest(
            model="claude-sonnet-4",
            max_tokens=1024,
            messages=[MessageContent(role="user", content="Hi")],
        )
        assert req.system is None
        assert req.stream is False
        assert req.temperature == 1.0
        assert req.top_p is None
        assert req.stop_sequences is None
        assert req.metadata is None

    def test_system_field_accepted(self) -> None:
        """The top-level system field should be accepted."""
        req = MessagesRequest(
            model="claude-sonnet-4",
            max_tokens=1024,
            messages=[MessageContent(role="user", content="Hi")],
            system="You are a helpful assistant.",
        )
        assert req.system == "You are a helpful assistant."

    def test_content_blocks_accepted(self) -> None:
        """Content can be a list of ContentBlockParam objects."""
        req = MessagesRequest(
            model="claude-sonnet-4",
            max_tokens=1024,
            messages=[
                MessageContent(
                    role="user",
                    content=[ContentBlockParam(type="text", text="Hello")],
                ),
            ],
        )
        assert isinstance(req.messages[0].content, list)

    def test_invalid_role_raises_error(self) -> None:
        """System role is not allowed in Anthropic messages."""
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="claude-sonnet-4",
                max_tokens=1024,
                messages=[
                    MessageContent(role="system", content="Hi"),
                ],
            )

    def test_serialization_round_trip(self) -> None:
        """Request should round-trip through JSON serialization."""
        original = MessagesRequest(
            model="claude-sonnet-4",
            max_tokens=2048,
            messages=[MessageContent(role="user", content="Hi")],
            system="Be concise.",
            temperature=0.5,
        )
        data = original.model_dump()
        restored = MessagesRequest(**data)
        assert restored.model == original.model
        assert restored.max_tokens == original.max_tokens
        assert restored.system == original.system
        assert restored.temperature == original.temperature


class TestAnthropicMessagesResponse:
    """Tests for the Anthropic MessagesResponse schema."""

    def test_valid_response(self) -> None:
        """A fully populated response should validate."""
        resp = MessagesResponse(
            id="msg_abc123def456",
            content=[TextBlock(text="Hello!")],
            model="claude-sonnet-4",
            stop_reason="end_turn",
            usage=AnthropicUsage(input_tokens=10, output_tokens=5),
        )
        assert resp.type == "message"
        assert resp.role == "assistant"
        assert resp.content[0].text == "Hello!"

    def test_default_type_and_role(self) -> None:
        """type='message' and role='assistant' should be defaults."""
        resp = MessagesResponse(
            id="msg_test",
            content=[TextBlock(text="Hi")],
            model="claude-sonnet-4",
        )
        assert resp.type == "message"
        assert resp.role == "assistant"

    def test_serialization_round_trip(self) -> None:
        """Response should round-trip through JSON serialization."""
        resp = MessagesResponse(
            id="msg_test123",
            content=[TextBlock(text="Test response")],
            model="claude-sonnet-4",
            stop_reason="end_turn",
            usage=AnthropicUsage(input_tokens=5, output_tokens=3),
        )
        json_str = resp.model_dump_json()
        restored = MessagesResponse.model_validate_json(json_str)
        assert restored.id == resp.id
        assert restored.content[0].text == "Test response"


class TestAnthropicStreamingEventSchemas:
    """Tests for Anthropic streaming event schemas."""

    def test_message_start_event(self) -> None:
        """MessageStartEvent should contain a MessagesResponse."""
        event = MessageStartEvent(
            message=MessagesResponse(
                id="msg_test",
                content=[],
                model="claude-sonnet-4",
                stop_reason=None,
                usage=AnthropicUsage(input_tokens=0, output_tokens=0),
            )
        )
        assert event.type == "message_start"
        assert event.message.id == "msg_test"

    def test_content_block_start_event(self) -> None:
        """ContentBlockStartEvent should contain a TextBlock."""
        event = ContentBlockStartEvent(
            index=0,
            content_block=TextBlock(text=""),
        )
        assert event.type == "content_block_start"
        assert event.index == 0

    def test_content_block_delta_event(self) -> None:
        """ContentBlockDeltaEvent should contain a TextDelta."""
        event = ContentBlockDeltaEvent(
            index=0,
            delta=TextDelta(text="Hello"),
        )
        assert event.type == "content_block_delta"
        assert event.delta.text == "Hello"

    def test_content_block_stop_event(self) -> None:
        """ContentBlockStopEvent should have the correct type."""
        event = ContentBlockStopEvent(index=0)
        assert event.type == "content_block_stop"

    def test_message_delta_event(self) -> None:
        """MessageDeltaEvent should contain stop_reason and usage."""
        event = MessageDeltaEvent(
            delta=MessageDeltaPayload(stop_reason="end_turn"),
            usage=MessageDeltaUsage(output_tokens=42),
        )
        assert event.type == "message_delta"
        assert event.delta.stop_reason == "end_turn"
        assert event.usage.output_tokens == 42

    def test_message_stop_event(self) -> None:
        """MessageStopEvent should have type='message_stop'."""
        event = MessageStopEvent()
        assert event.type == "message_stop"

    def test_ping_event(self) -> None:
        """PingEvent should have type='ping'."""
        event = PingEvent()
        assert event.type == "ping"


class TestAnthropicErrorSchema:
    """Tests for Anthropic error response schemas."""

    def test_error_response(self) -> None:
        """An AnthropicErrorResponse should have the correct structure."""
        err = AnthropicErrorResponse(
            error=AnthropicErrorDetail(
                type="api_error",
                message="Something went wrong",
            )
        )
        assert err.type == "error"
        assert err.error.type == "api_error"
        assert err.error.message == "Something went wrong"

    def test_error_serialization(self) -> None:
        """Error response should serialize to the correct JSON structure."""
        err = AnthropicErrorResponse(
            error=AnthropicErrorDetail(
                type="invalid_request_error",
                message="Missing required field",
            )
        )
        data = err.model_dump()
        assert data["type"] == "error"
        assert data["error"]["type"] == "invalid_request_error"
        assert data["error"]["message"] == "Missing required field"
