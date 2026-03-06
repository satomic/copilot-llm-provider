"""
Tests for the OpenAI-compatible chat completions endpoint.

Covers non-streaming, streaming (SSE), model passthrough, and error handling.
All tests use the MockProvider from conftest — no real Copilot SDK calls.
"""

import json

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

ENDPOINT = "/v1/chat/completions"

# A minimal valid request body
VALID_REQUEST = {
    "model": "gpt-4.1",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
}


# =============================================================================
# Non-streaming tests
# =============================================================================


async def test_non_streaming_returns_valid_openai_response(
    client: AsyncClient,
) -> None:
    """POST /v1/chat/completions (non-stream) returns a valid OpenAI response."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    assert response.status_code == 200

    body = response.json()
    assert "id" in body
    assert body["object"] == "chat.completion"
    assert "choices" in body
    assert "usage" in body


async def test_non_streaming_response_has_required_fields(
    client: AsyncClient,
) -> None:
    """Response must contain id, object, created, model, choices, and usage."""
    response = await client.post(ENDPOINT, json=VALID_REQUEST)
    body = response.json()

    assert isinstance(body["id"], str)
    assert body["object"] == "chat.completion"
    assert isinstance(body["created"], int)
    assert isinstance(body["model"], str)
    assert isinstance(body["choices"], list)
    assert len(body["choices"]) >= 1

    choice = body["choices"][0]
    assert "message" in choice
    assert choice["message"]["role"] == "assistant"
    assert isinstance(choice["message"]["content"], str)
    assert "finish_reason" in choice

    usage = body["usage"]
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage


async def test_non_streaming_model_is_passed_through(
    client: AsyncClient,
) -> None:
    """The model field in the response should match the requested model."""
    request = {**VALID_REQUEST, "model": "gpt-4.1"}
    response = await client.post(ENDPOINT, json=request)
    body = response.json()
    assert body["model"] == "gpt-4.1"


async def test_non_streaming_with_custom_temperature(
    client: AsyncClient,
) -> None:
    """Request with custom temperature should not fail."""
    request = {**VALID_REQUEST, "temperature": 0.5}
    response = await client.post(ENDPOINT, json=request)
    assert response.status_code == 200


async def test_non_streaming_with_max_tokens(
    client: AsyncClient,
) -> None:
    """Request with max_tokens should not fail."""
    request = {**VALID_REQUEST, "max_tokens": 100}
    response = await client.post(ENDPOINT, json=request)
    assert response.status_code == 200


# =============================================================================
# Streaming tests
# =============================================================================


async def test_streaming_returns_sse_content_type(
    client: AsyncClient,
) -> None:
    """POST /v1/chat/completions with stream=true returns text/event-stream."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


async def test_streaming_sse_lines_start_with_data(
    client: AsyncClient,
) -> None:
    """Each SSE line must start with 'data: '."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    raw_text = response.text
    lines = [line for line in raw_text.strip().split("\n") if line.strip()]
    assert len(lines) >= 2, f"Expected at least 2 SSE lines, got {len(lines)}"

    for line in lines:
        assert line.startswith("data: "), f"SSE line does not start with 'data: ': {line!r}"


async def test_streaming_ends_with_done(
    client: AsyncClient,
) -> None:
    """The SSE stream must end with 'data: [DONE]'."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    raw_text = response.text
    lines = [line for line in raw_text.strip().split("\n") if line.strip()]
    assert lines[-1] == "data: [DONE]"


async def test_streaming_chunks_are_valid_json(
    client: AsyncClient,
) -> None:
    """Each SSE data line (except [DONE]) must be valid JSON."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    raw_text = response.text
    lines = [line for line in raw_text.strip().split("\n") if line.strip()]

    for line in lines:
        assert line.startswith("data: ")
        payload = line[len("data: "):]
        if payload == "[DONE]":
            continue
        # Must be valid JSON
        chunk = json.loads(payload)
        assert isinstance(chunk, dict)


async def test_streaming_chunks_match_chunk_schema(
    client: AsyncClient,
) -> None:
    """Each streaming chunk must match the ChatCompletionChunk schema."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    raw_text = response.text
    lines = [line for line in raw_text.strip().split("\n") if line.strip()]

    json_chunks = []
    for line in lines:
        payload = line[len("data: "):]
        if payload == "[DONE]":
            continue
        json_chunks.append(json.loads(payload))

    assert len(json_chunks) >= 1, "Expected at least one JSON chunk before [DONE]"

    for chunk in json_chunks:
        assert "id" in chunk
        assert chunk["object"] == "chat.completion.chunk"
        assert "created" in chunk
        assert "model" in chunk
        assert "choices" in chunk
        assert isinstance(chunk["choices"], list)
        assert len(chunk["choices"]) >= 1
        assert "delta" in chunk["choices"][0]


async def test_streaming_first_chunk_has_assistant_role(
    client: AsyncClient,
) -> None:
    """The first streaming chunk should include role='assistant' in delta."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    raw_text = response.text
    lines = [line for line in raw_text.strip().split("\n") if line.strip()]

    first_payload = lines[0][len("data: "):]
    first_chunk = json.loads(first_payload)
    delta = first_chunk["choices"][0]["delta"]
    assert delta.get("role") == "assistant"


async def test_streaming_final_chunk_has_finish_reason(
    client: AsyncClient,
) -> None:
    """One of the chunks should contain finish_reason='stop'."""
    request = {**VALID_REQUEST, "stream": True}
    response = await client.post(ENDPOINT, json=request)

    raw_text = response.text
    lines = [line for line in raw_text.strip().split("\n") if line.strip()]

    finish_reasons = []
    for line in lines:
        payload = line[len("data: "):]
        if payload == "[DONE]":
            continue
        chunk = json.loads(payload)
        fr = chunk["choices"][0].get("finish_reason")
        if fr is not None:
            finish_reasons.append(fr)

    assert "stop" in finish_reasons


# =============================================================================
# Error handling tests
# =============================================================================


async def test_provider_failure_returns_error_response(
    failing_client: AsyncClient,
) -> None:
    """When the provider raises an error, the endpoint returns an error JSON."""
    response = await failing_client.post(ENDPOINT, json=VALID_REQUEST)
    # The endpoint catches exceptions and returns a JSON error
    assert response.status_code == 500

    body = response.json()
    assert "error" in body
    assert "message" in body["error"]
    assert "type" in body["error"]


async def test_missing_model_field_returns_422(
    client: AsyncClient,
) -> None:
    """A request missing the required 'model' field should return 422."""
    bad_request = {
        "messages": [{"role": "user", "content": "Hi"}],
    }
    response = await client.post(ENDPOINT, json=bad_request)
    assert response.status_code == 422


async def test_missing_messages_field_returns_422(
    client: AsyncClient,
) -> None:
    """A request missing the required 'messages' field should return 422."""
    bad_request = {"model": "gpt-4.1"}
    response = await client.post(ENDPOINT, json=bad_request)
    assert response.status_code == 422
