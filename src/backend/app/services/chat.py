"""
Chat service — orchestrates chat completion requests.

Sits between the API layer and the Provider layer. Responsible for:
- Delegating to the provider for completion
- Logging request lifecycle (model, message count, timing)
- Future: usage tracking, rate limiting, caching

This is intentionally a thin pass-through layer. The business logic
lives in the Provider; the HTTP logic lives in the API layer. This
service adds observability (logging + timing) and serves as the
natural extension point for cross-cutting concerns.
"""

import logging
import time
from collections.abc import AsyncGenerator

from src.backend.app.providers.base import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    Provider,
    StreamDelta,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Service layer for chat completion operations.

    Args:
        provider: The LLM provider to delegate completions to.
    """

    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    async def complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Handle a non-streaming chat completion request.

        Delegates to the provider and logs timing information.

        Args:
            request: The chat completion request.

        Returns:
            The full chat completion response.

        Raises:
            ValueError: If the request is invalid.
            RuntimeError: If the provider encounters an error.
        """
        logger.info(
            "Chat completion request: model=%s, messages=%d, stream=False",
            request.model,
            len(request.messages),
        )

        start = time.monotonic()
        try:
            response = await self._provider.chat_completion(request)
            elapsed = time.monotonic() - start

            logger.info(
                "Chat completion response: model=%s, id=%s, "
                "content_len=%d, finish_reason=%s, elapsed=%.3fs",
                response.model,
                response.id,
                len(response.content),
                response.finish_reason,
                elapsed,
            )
            return response
        except Exception:
            elapsed = time.monotonic() - start
            logger.exception(
                "Chat completion failed: model=%s, elapsed=%.3fs",
                request.model,
                elapsed,
            )
            raise

    async def complete_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Handle a streaming chat completion request.

        Delegates to the provider's streaming method, wrapping the
        async generator with logging for the start, chunk count, and
        completion of the stream.

        Args:
            request: The chat completion request.

        Yields:
            StreamDelta objects as they arrive from the provider.

        Raises:
            ValueError: If the request is invalid.
            RuntimeError: If the provider encounters an error.
        """
        logger.info(
            "Chat completion stream request: model=%s, messages=%d, stream=True",
            request.model,
            len(request.messages),
        )

        start = time.monotonic()
        chunk_count = 0

        try:
            async for delta in self._provider.chat_completion_stream(request):
                chunk_count += 1
                yield delta

            elapsed = time.monotonic() - start
            logger.info(
                "Chat completion stream complete: model=%s, chunks=%d, elapsed=%.3fs",
                request.model,
                chunk_count,
                elapsed,
            )
        except Exception:
            elapsed = time.monotonic() - start
            logger.exception(
                "Chat completion stream failed: model=%s, chunks=%d, elapsed=%.3fs",
                request.model,
                chunk_count,
                elapsed,
            )
            raise
