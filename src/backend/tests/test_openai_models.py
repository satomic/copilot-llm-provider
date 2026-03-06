"""
Tests for the OpenAI-compatible models listing endpoint.

Covers response format, structure of individual model objects,
and error handling when the provider fails.
"""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

ENDPOINT = "/v1/models"


async def test_list_models_returns_200(client: AsyncClient) -> None:
    """GET /v1/models should return 200."""
    response = await client.get(ENDPOINT)
    assert response.status_code == 200


async def test_list_models_returns_valid_model_list_format(
    client: AsyncClient,
) -> None:
    """Response must have object='list' and a 'data' array."""
    response = await client.get(ENDPOINT)
    body = response.json()

    assert body["object"] == "list"
    assert "data" in body
    assert isinstance(body["data"], list)


async def test_list_models_data_contains_models(
    client: AsyncClient,
) -> None:
    """The data array should contain the mock models."""
    response = await client.get(ENDPOINT)
    body = response.json()

    data = body["data"]
    assert len(data) == 2  # MockProvider returns 2 models


async def test_each_model_has_required_fields(
    client: AsyncClient,
) -> None:
    """Each model object must have id, object, created, owned_by."""
    response = await client.get(ENDPOINT)
    body = response.json()

    for model in body["data"]:
        assert "id" in model
        assert isinstance(model["id"], str)
        assert model["object"] == "model"
        assert "created" in model
        assert isinstance(model["created"], int)
        assert "owned_by" in model
        assert isinstance(model["owned_by"], str)


async def test_model_ids_match_mock_provider(
    client: AsyncClient,
) -> None:
    """Model IDs in the response should match the MockProvider's models."""
    response = await client.get(ENDPOINT)
    body = response.json()

    model_ids = {m["id"] for m in body["data"]}
    assert "gpt-4.1" in model_ids
    assert "claude-sonnet-4" in model_ids


async def test_model_owned_by_is_copilot(
    client: AsyncClient,
) -> None:
    """The owned_by field should be 'copilot' for all models."""
    response = await client.get(ENDPOINT)
    body = response.json()

    for model in body["data"]:
        assert model["owned_by"] == "copilot"


async def test_list_models_provider_failure_returns_error(
    failing_client: AsyncClient,
) -> None:
    """When the provider fails, /v1/models returns an error response."""
    response = await failing_client.get(ENDPOINT)
    assert response.status_code == 500

    body = response.json()
    assert "error" in body
    assert "message" in body["error"]
    assert "type" in body["error"]
