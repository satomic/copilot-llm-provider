"""
Tests for the health endpoint.

Verifies that GET /health returns the expected status and version,
and that the endpoint does not require authentication.
"""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_health_returns_200_with_status_ok(client: AsyncClient) -> None:
    """GET /health should return 200 with status=ok and version."""
    response = await client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


async def test_health_response_has_expected_keys(client: AsyncClient) -> None:
    """GET /health response must contain exactly 'status' and 'version' keys."""
    response = await client.get("/health")
    body = response.json()
    assert set(body.keys()) == {"status", "version"}


async def test_health_does_not_require_auth(auth_client: AsyncClient) -> None:
    """GET /health should succeed even when API_KEY is configured and no key is sent.

    The health endpoint is intentionally unprotected so monitoring tools
    can hit it without credentials.
    """
    response = await auth_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
