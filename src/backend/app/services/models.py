"""
Model service — manages model discovery and caching.

Responsible for:
- Querying the provider for available models
- Caching model lists to avoid repeated SDK calls
- Periodic cache refresh (TTL-based expiry)
- Looking up individual models by ID
"""

import asyncio
import logging
import time

from src.backend.app.providers.base import ModelInfo, Provider

logger = logging.getLogger(__name__)

# Default cache time-to-live: 5 minutes.
DEFAULT_CACHE_TTL_SECONDS: float = 300.0


class ModelService:
    """Service layer for model listing and discovery.

    Wraps Provider.list_models() with a TTL-based in-memory cache
    protected by an asyncio.Lock for thread safety. Multiple concurrent
    callers hitting an expired cache will only trigger one provider call;
    the others will wait on the lock and then read the refreshed cache.

    Args:
        provider: The LLM provider to query for models.
        cache_ttl: Cache time-to-live in seconds. Defaults to 5 minutes.
    """

    def __init__(
        self,
        provider: Provider,
        cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._provider = provider
        self._cache_ttl = cache_ttl
        self._cache: list[ModelInfo] = []
        self._cache_timestamp: float = 0.0
        self._lock = asyncio.Lock()

    def _cache_is_valid(self) -> bool:
        """Return True if the cache exists and has not expired."""
        if not self._cache:
            return False
        return (time.monotonic() - self._cache_timestamp) < self._cache_ttl

    async def list_models(self) -> list[ModelInfo]:
        """Return the list of available models.

        Returns cached results if the cache is still valid. Otherwise
        refreshes the cache from the provider (under a lock to prevent
        thundering-herd duplicate calls).

        Returns:
            A list of ModelInfo objects.

        Raises:
            RuntimeError: If the provider fails to list models.
        """
        if self._cache_is_valid():
            logger.debug("Returning %d cached models", len(self._cache))
            return list(self._cache)

        # Cache miss or expired — refresh under lock.
        async with self._lock:
            # Double-check after acquiring lock (another coroutine may
            # have refreshed the cache while we were waiting).
            if self._cache_is_valid():
                logger.debug(
                    "Cache refreshed by another coroutine; returning %d models",
                    len(self._cache),
                )
                return list(self._cache)

            logger.info("Refreshing model cache from provider...")
            try:
                models = await self._provider.list_models()
                self._cache = models
                self._cache_timestamp = time.monotonic()
                logger.info("Model cache refreshed: %d models", len(models))
                return list(self._cache)
            except Exception:
                logger.exception("Failed to refresh model cache")
                # If we have stale data, return it rather than failing.
                if self._cache:
                    logger.warning(
                        "Returning stale model cache (%d models) after refresh failure",
                        len(self._cache),
                    )
                    return list(self._cache)
                raise

    async def get_model(self, model_id: str) -> ModelInfo | None:
        """Look up a specific model by its ID.

        Args:
            model_id: The unique model identifier to look up.

        Returns:
            The ModelInfo if found, or None if the model doesn't exist.
        """
        models = await self.list_models()
        for model in models:
            if model.id == model_id:
                return model
        logger.debug("Model not found: %s", model_id)
        return None

    async def refresh_cache(self) -> None:
        """Force a refresh of the cached model list.

        Invalidates the current cache timestamp, causing the next
        list_models() call to fetch fresh data. Then triggers a fetch.
        """
        logger.info("Forcing model cache refresh")
        # Invalidate the cache so the next call fetches fresh data.
        self._cache_timestamp = 0.0
        await self.list_models()
