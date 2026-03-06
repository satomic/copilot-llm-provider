"""
Tests for the Anthropic-compatible messages endpoint.

Covers non-streaming, streaming (SSE with named events), system message handling,
and error handling. All tests use the MockProvider from conftest.
"""

import json

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

ENDPOINT = "/v1/messages"

# A minimal valid Anthropic request body
VALID_REQUEST = {
    "model": "claude-sonnet-4",
    "max_tokens": 1024,
    "messages": [
        {"role": "user", "content": "Hello!"},
    ],
}


# =============================================================================
# Non-streaming tests
# =============================================================================


async def test_non_streaming_returns_valid_anthropic_response(
    client: AsyncClient,
) -> None:
    """POST /v1/messages (non-stream) returns a valid Anthropic response."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    assert response.status_code == 200

    body = response.json()
    assert body["type"] == "message"
    assert body["role"] == "assistant"
    assert "id" in body
    assert "content" in body
    assert "stop_reason" in body


async def test_non_streaming_response_id_starts_with_msg(
    client: AsyncClient,
) -> None:
    """Anthropic response IDs must start with 'msg_'."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    body = response.json()
    assert body["id"].startswith("msg_")


async def test_non_streaming_response_has_content_blocks(
    client: AsyncClient,
) -> None:
    """Response content must be a list of content blocks with type='text'."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    body = response.json()

    content = body["content"]
    assert isinstance(content, list)
    assert len(content) >= 1
    assert content[0]["type"] == "text"
    assert isinstance(content[0]["text"], str)
    assert len(content[0]["text"]) > 0


async def test_non_streaming_response_has_usage(
    client: AsyncClient,
) -> None:
    """Response must contain usage with input_tokens and output_tokens."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    body = response.json()

    usage = body["usage"]
    assert "input_tokens" in usage
    assert "output_tokens" in usage
    assert isinstance(usage["input_tokens"], int)
    assert isinstance(usage["output_tokens"], int)


async def test_non_streaming_stop_reason(
    client: AsyncClient,
) -> None:
    """The stop_reason should be 'end_turn' for a normal completion."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    body = response.json()
    assert body["stop_reason"] == "end_turn"


async def test_system_message_is_handled(
    client: AsyncClient,
) -> None:
    """A top-level 'system' field should be accepted and not cause errors."""
    request = {
        **VALID_REQUEST,
        "system": "You are a helpful assistant.",
    }
    response = await client.post(ENDPOINT, json=request)
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "message"


async def test_model_field_is_passed_through(
    client: AsyncClient,
) -> None:
    """The model in the response should match the requested model."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    body = response.json()
    assert body["model"] == "claude-sonnet-4"


# =============================================================================
# Streaming tests
# =============================================================================


def _parse_sse_events(raw_text: str) -> list[tuple[str, dict]]:
    """Parse SSE text into a list of (event_type, data_dict) tuples."""
    events = []
    current_event_type = None
    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("event: "):
            current_event_type = line[len("event: "):]
        elif line.startswith("data: "):
            data_str = line[len("data: "):]
            data = json.loads(data_str)
            events.append((current_event_type, data))
            current_event_type = None
    return events


async def test_streaming_returns_sse_content_type(
    client: AsyncClient,
) -> None:
    """POST /v1/messages with stream=true returns text/event-stream."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


async def test_streaming_events_have_event_and_data_lines(
    client: AsyncClient,
) -> None:
    """Anthropic SSE events must have both 'event: ' and 'data: ' lines."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    raw = response.text
    lines = [l for l in raw.split("\n") if l.strip()]

    # There should be pairs of event: and data: lines
    event_lines = [l for l in lines if l.startswith("event: ")]
    data_lines = [l for l in lines if l.startswith("data: ")]

    assert len(event_lines) >= 4, "Expected at least 4 event type lines"
    assert len(data_lines) >= 4, "Expected at least 4 data lines"
    assert len(event_lines) == len(data_lines), "Each event line should pair with a data line"


async def test_streaming_event_sequence(
    client: AsyncClient,
) -> None:
    """The event sequence should follow the Anthropic specification:
    message_start -> content_block_start -> ping -> content_block_delta(s) ->
    content_block_stop -> message_delta -> message_stop
    """
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    events = _parse_sse_events(response.text)
    event_types = [e[0] for e in events]

    # Check required events are present
    assert "message_start" in event_types
    assert "content_block_start" in event_types
    assert "content_block_stop" in event_types
    assert "message_delta" in event_types
    assert "message_stop" in event_types

    # Check ordering: message_start is first
    assert event_types[0] == "message_start"
    # message_stop is last
    assert event_types[-1] == "message_stop"
    # message_delta is second to last
    assert event_types[-2] == "message_delta"
    # content_block_stop is before message_delta
    assert event_types.index("content_block_stop") < event_types.index("message_delta")
    # content_block_start is before any content_block_delta
    if "content_block_delta" in event_types:
        assert event_types.index("content_block_start") < event_types.index(
            "content_block_delta"
        )


async def test_streaming_message_start_event_structure(
    client: AsyncClient,
) -> None:
    """The message_start event should contain a message object."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    events = _parse_sse_events(response.text)
    message_start = next(data for etype, data in events if etype == "message_start")

    assert message_start["type"] == "message_start"
    assert "message" in message_start

    msg = message_start["message"]
    assert msg["type"] == "message"
    assert msg["role"] == "assistant"
    assert msg["id"].startswith("msg_")
    assert isinstance(msg["content"], list)


async def test_streaming_content_block_delta_has_text(
    client: AsyncClient,
) -> None:
    """content_block_delta events should contain text deltas."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    events = _parse_sse_events(response.text)
    deltas = [data for etype, data in events if etype == "content_block_delta"]

    assert len(deltas) >= 1, "Expected at least one content_block_delta event"

    for delta_event in deltas:
        assert delta_event["type"] == "content_block_delta"
        assert "delta" in delta_event
        assert delta_event["delta"]["type"] == "text_delta"
        assert "text" in delta_event["delta"]
        assert isinstance(delta_event["delta"]["text"], str)


async def test_streaming_message_delta_has_stop_reason(
    client: AsyncClient,
) -> None:
    """The message_delta event should contain the stop_reason."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    events = _parse_sse_events(response.text)
    message_delta = next(data for etype, data in events if etype == "message_delta")

    assert message_delta["type"] == "message_delta"
    assert "delta" in message_delta
    assert "stop_reason" in message_delta["delta"]
    assert message_delta["delta"]["stop_reason"] == "end_turn"


async def test_streaming_message_delta_has_usage(
    client: AsyncClient,
) -> None:
    """The message_delta event should contain output_tokens usage."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    events = _parse_sse_events(response.text)
    message_delta = next(data for etype, data in events if etype == "message_delta")

    assert "usage" in message_delta
    assert "output_tokens" in message_delta["usage"]
    assert isinstance(message_delta["usage"]["output_tokens"], int)


# =============================================================================
# Error handling
# =============================================================================


async def test_provider_failure_returns_anthropic_error(
    failing_client: AsyncClient,
) -> None:
    """When the provider fails, the endpoint returns an Anthropic-format error."""
    response = await failing_client.post(ENDPOINT, json=VALID_REQUEST)
    assert response.status_code == 500

    body = response.json()
    assert body["type"] == "error"
    assert "error" in body
    assert "type" in body["error"]
    assert "message" in body["error"]


async def test_missing_max_tokens_returns_422(
    client: AsyncClient,
) -> None:
    """Anthropic requires max_tokens; omitting it should return 422."""
    bad_request = {
        "model": "claude-sonnet-4",
        "messages": [{"role": "user", "content": "Hello"}],
        # max_tokens is missing
    }
    response = await client.post(ENDPOINT, json=bad_request)
    assert response.status_code == 422


async def test_missing_model_returns_422(
    client: AsyncClient,
) -> None:
    """Omitting the required 'model' field should return 422."""
    bad_request = {
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello"}],
    }
    response = await client.post(ENDPOINT, json=bad_request)
    assert response.status_code == 422
