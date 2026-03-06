"""
Pytest configuration and shared fixtures.

Provides reusable test fixtures for the backend test suite.
All fixtures mock the Provider interface so tests never call the real Copilot SDK.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.app.core.config import Settings
from src.backend.app.core.dependencies import get_provider, get_settings
from src.backend.app.providers.base import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelInfo,
    Provider,
    StreamDelta,
    Usage,
)


# =============================================================================
# Mock Provider
# =============================================================================


class MockProvider(Provider):
    """A fake Provider that returns predictable, schema-compliant responses.

    Does NOT call the real Copilot SDK. All methods return hard-coded data
    that matches the internal data models exactly.
    """

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="gpt-4.1", name="GPT-4.1", provider="copilot"),
            ModelInfo(id="claude-sonnet-4", name="Claude Sonnet 4", provider="copilot"),
        ]

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id="chatcmpl-test123456789000",
            model=request.model,
            content="Hello! This is a mock response.",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            finish_reason="stop",
        )

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        deltas = [
            StreamDelta(
                id="chatcmpl-stream-test-0001",
                model=request.model,
                delta_content="Hello",
                finish_reason=None,
            ),
            StreamDelta(
                id="chatcmpl-stream-test-0001",
                model=request.model,
                delta_content=" world",
                finish_reason=None,
            ),
            StreamDelta(
                id="chatcmpl-stream-test-0001",
                model=request.model,
                delta_content="!",
                finish_reason=None,
            ),
            StreamDelta(
                id="chatcmpl-stream-test-0001",
                model=request.model,
                delta_content=None,
                finish_reason="stop",
            ),
        ]
        for delta in deltas:
            yield delta


class FailingProvider(Provider):
    """A Provider that always raises RuntimeError, used for error-path tests."""

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def list_models(self) -> list[ModelInfo]:
        raise RuntimeError("Provider failure: cannot list models")

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        raise RuntimeError("Provider failure: chat completion error")

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        raise RuntimeError("Provider failure: streaming error")
        yield  # type: ignore[misc]  # pragma: no cover


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def settings() -> Settings:
    """Create a test Settings instance with safe defaults (no real token)."""
    return Settings(
        github_token="test-token-not-real",
        api_key=None,
        host="127.0.0.1",
        port=8000,
        cors_origins=["*"],
        log_level="debug",
        frontend_dir=None,
    )


@pytest.fixture
def settings_with_auth() -> Settings:
    """Create a test Settings instance that requires API key authentication."""
    return Settings(
        github_token="test-token-not-real",
        api_key="test-secret-key-12345",
        host="127.0.0.1",
        port=8000,
        cors_origins=["*"],
        log_level="debug",
        frontend_dir=None,
    )


@pytest.fixture
def mock_provider() -> MockProvider:
    """Return a MockProvider that produces predictable responses."""
    return MockProvider()


@pytest.fixture
def failing_provider() -> FailingProvider:
    """Return a FailingProvider that always raises errors."""
    return FailingProvider()


def _build_app_with_overrides(
    provider: Provider,
    test_settings: Settings,
):
    """Build a fresh FastAPI app with dependency overrides for testing.

    This avoids importing the module-level ``app`` which triggers the
    real lifespan (and CopilotProvider). Instead we call ``create_app()``
    and override dependencies before any request is handled.

    The verify_api_key dependency calls get_settings() directly (not through
    Depends), so we must also seed the lru_cache with our test settings.
    We do this by clearing the cache first, then calling get_settings once
    with monkeypatching-style replacement so the cached value is ours.
    """
    from unittest.mock import patch

    from src.backend.app.main import create_app

    # Clear the lru_cache so the next call to get_settings() builds fresh.
    get_settings.cache_clear()

    # Patch Settings() constructor to return our test settings, then call
    # get_settings() once to populate the lru_cache with the test instance.
    with patch("src.backend.app.core.dependencies.Settings", return_value=test_settings):
        cached = get_settings()  # Seeds the lru_cache with test_settings
    assert cached is test_settings

    application = create_app()

    # Inject the mock provider into app.state so get_provider works
    application.state.provider = provider

    # Override the DI functions for FastAPI-level resolution
    application.dependency_overrides[get_settings] = lambda: test_settings
    application.dependency_overrides[get_provider] = lambda: provider

    return application


@pytest.fixture
async def test_app(mock_provider: MockProvider, settings: Settings):
    """FastAPI app with the mock provider injected (no auth required)."""
    app = _build_app_with_overrides(mock_provider, settings)
    yield app
    # Clean up lru_cache after test
    get_settings.cache_clear()


@pytest.fixture
async def test_app_with_auth(mock_provider: MockProvider, settings_with_auth: Settings):
    """FastAPI app with mock provider and API key authentication enabled."""
    app = _build_app_with_overrides(mock_provider, settings_with_auth)
    yield app
    get_settings.cache_clear()


@pytest.fixture
async def test_app_failing(failing_provider: FailingProvider, settings: Settings):
    """FastAPI app with a failing provider for error-path tests."""
    app = _build_app_with_overrides(failing_provider, settings)
    yield app
    get_settings.cache_clear()


@pytest.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient wired to the test app (no auth)."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def auth_client(test_app_with_auth) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient wired to the auth-enabled test app."""
    transport = ASGITransport(app=test_app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def failing_client(test_app_failing) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient wired to the failing-provider test app."""
    transport = ASGITransport(app=test_app_failing)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
