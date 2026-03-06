"""
Session pool — manages CopilotClient session lifecycle.

The Copilot SDK uses stateful sessions (they accumulate message history).
For a stateless HTTP API, we need to manage session lifecycle carefully:

Current strategy: Per-request sessions.
    - Each API request creates a fresh session.
    - The session is destroyed after the response completes.
    - Simple and correct, but has session-creation overhead.

Future optimization: Session pooling with history reset.
    - Maintain a pool of idle sessions.
    - Clear message history before reusing a session.
    - Reduces latency by avoiding session creation per request.

Concurrency control:
    - Limits the number of concurrent sessions to prevent resource exhaustion.
    - Each session corresponds to state within the CopilotClient child process.
"""

import asyncio
import logging
from typing import Any

from copilot.types import PermissionHandler

logger = logging.getLogger(__name__)


class SessionPool:
    """Manages a pool of CopilotClient sessions.

    Controls session creation, reuse, and destruction. Enforces
    concurrency limits to prevent resource exhaustion.

    Uses asyncio.Semaphore to throttle concurrent sessions. When the
    maximum is reached, acquire() will block until a session is released.

    Args:
        client: The CopilotClient instance to create sessions from.
        max_sessions: Maximum number of concurrent sessions allowed.
    """

    def __init__(self, client: Any, max_sessions: int = 10) -> None:
        self._client = client
        self._max_sessions = max_sessions
        self._semaphore = asyncio.Semaphore(max_sessions)
        # Track active sessions so we can destroy them all on shutdown.
        self._active_sessions: set[Any] = set()
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        """Return the number of currently active sessions."""
        return len(self._active_sessions)

    @property
    def max_sessions(self) -> int:
        """Return the configured maximum concurrent session count."""
        return self._max_sessions

    async def acquire(self, model: str, **kwargs: Any) -> Any:
        """Acquire a session for the given model.

        Creates a new session via the CopilotClient. Blocks (awaits) if
        the maximum concurrent session limit is reached, resuming once
        another session is released.

        Args:
            model: The model ID to configure the session for.
            **kwargs: Additional session config (e.g., streaming=True).

        Returns:
            A CopilotClient session object ready for use.

        Raises:
            RuntimeError: If session creation fails.
        """
        logger.debug(
            "Acquiring session for model=%s (active=%d, max=%d)",
            model,
            self.active_count,
            self._max_sessions,
        )

        await self._semaphore.acquire()

        try:
            session_config: dict[str, Any] = {
                "model": model,
                "on_permission_request": PermissionHandler.approve_all,
                **kwargs,
            }
            session = await self._client.create_session(session_config)
        except Exception:
            # Release the semaphore slot since we failed to create a session.
            self._semaphore.release()
            logger.exception("Failed to create session for model=%s", model)
            raise RuntimeError(
                f"Failed to create session for model={model}"
            ) from None

        async with self._lock:
            self._active_sessions.add(session)

        logger.debug(
            "Session acquired for model=%s (active=%d)", model, self.active_count
        )
        return session

    async def release(self, session: Any) -> None:
        """Release a session back to the pool (or destroy it).

        In the current per-request strategy, this destroys the session
        and frees the semaphore slot for the next caller.

        Args:
            session: The session to release.
        """
        try:
            await session.destroy()
            logger.debug("Session destroyed during release")
        except Exception:
            logger.warning("Failed to destroy session during release", exc_info=True)
        finally:
            async with self._lock:
                self._active_sessions.discard(session)
            self._semaphore.release()
            logger.debug("Session released (active=%d)", self.active_count)

    async def close_all(self) -> None:
        """Destroy all sessions in the pool.

        Called during application shutdown. Ensures all sessions are
        properly cleaned up. Errors during individual session destruction
        are logged but do not prevent other sessions from being cleaned up.
        """
        async with self._lock:
            sessions = list(self._active_sessions)
            self._active_sessions.clear()

        if not sessions:
            logger.debug("close_all: no active sessions to destroy")
            return

        logger.info("Destroying %d active session(s)...", len(sessions))

        for session in sessions:
            try:
                await session.destroy()
            except Exception:
                logger.warning("Failed to destroy session during close_all", exc_info=True)
            finally:
                self._semaphore.release()

        logger.info("All sessions destroyed")
