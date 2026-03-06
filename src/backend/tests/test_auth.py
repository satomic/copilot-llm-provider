"""
Tests for authentication (API key verification).

Covers both no-auth mode (API_KEY not configured) and authenticated mode.
Uses the OpenAI /v1/models endpoint as the protected test target because
it's a simple GET that exercises the verify_api_key dependency.
"""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

# We use /v1/models as the test endpoint because it requires auth
# and is the simplest protected route (GET, no request body).
PROTECTED_ENDPOINT = "/v1/models"


# =============================================================================
# No-auth mode (API_KEY is not configured)
# =============================================================================


async def test_request_passes_when_no_api_key_configured(
    client: AsyncClient,
) -> None:
    """When API_KEY is None, requests should pass without any credentials."""
    response = await client.get(PROTECTED_ENDPOINT)
    assert response.status_code == 200


# =============================================================================
# Authenticated mode (API_KEY is configured)
# =============================================================================


async def test_request_passes_with_correct_x_api_key_header(
    auth_client: AsyncClient,
) -> None:
    """Request with a valid X-API-Key header should succeed."""
    response = await auth_client.get(
        PROTECTED_ENDPOINT,
        headers={"X-API-Key": "test-secret-key-12345"},
    )
    assert response.status_code == 200


async def test_request_passes_with_correct_bearer_token(
    auth_client: AsyncClient,
) -> None:
    """Request with a valid Authorization: Bearer token should succeed."""
    response = await auth_client.get(
        PROTECTED_ENDPOINT,
        headers={"Authorization": "Bearer test-secret-key-12345"},
    )
    assert response.status_code == 200


async def test_request_fails_with_wrong_api_key(
    auth_client: AsyncClient,
) -> None:
    """Request with an incorrect API key should return 401."""
    response = await auth_client.get(
        PROTECTED_ENDPOINT,
        headers={"X-API-Key": "wrong-key-99999"},
    )
    assert response.status_code == 401


async def test_request_fails_with_no_key_when_api_key_configured(
    auth_client: AsyncClient,
) -> None:
    """Request with no credentials when API_KEY is set should return 401."""
    response = await auth_client.get(PROTECTED_ENDPOINT)
    assert response.status_code == 401


async def test_error_response_matches_openai_error_schema(
    auth_client: AsyncClient,
) -> None:
    """Authentication error responses must follow the OpenAI error format:
    {"detail": {"error": {"message": "...", "type": "...", "code": ...}}}
    """
    response = await auth_client.get(PROTECTED_ENDPOINT)
    assert response.status_code == 401

    body = response.json()
    # FastAPI wraps HTTPException detail in a "detail" key
    assert "detail" in body
    error_wrapper = body["detail"]
    assert "error" in error_wrapper
    error = error_wrapper["error"]
    assert "message" in error
    assert "type" in error
    assert error["type"] == "authentication_error"
    assert "code" in error


async def test_bearer_token_is_case_insensitive_prefix(
    auth_client: AsyncClient,
) -> None:
    """The 'Bearer' prefix check should be case-insensitive."""
    response = await auth_client.get(
        PROTECTED_ENDPOINT,
        headers={"Authorization": "bearer test-secret-key-12345"},
    )
    assert response.status_code == 200
