"""
Multi-token pool service.

Manages multiple GitHub tokens (each backed by a separate CopilotProvider),
providing:
  - Round-robin token selection for fair distribution
  - Per-token quota tracking (premium request limits from GitHub)
  - Dynamic token CRUD with persistence
  - Health monitoring per token
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from uuid import uuid4

from src.backend.app.providers.copilot import CopilotProvider

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/github_tokens.json")


@dataclass
class TokenInfo:
    """Runtime state for a single GitHub token."""

    id: str
    alias: str
    token: str
    enabled: bool = True
    # Provider instance (created at startup)
    provider: CopilotProvider | None = field(default=None, repr=False)
    # Status
    status: str = "pending"  # pending | active | error | stopped
    error_message: str | None = None
    # Usage counters (in-memory, reset on restart)
    total_requests: int = 0
    premium_requests: int = 0
    # Quota from GitHub (fetched dynamically)
    premium_quota_limit: int | None = None
    premium_quota_used: int | None = None
    premium_quota_reset: str | None = None  # ISO timestamp
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_used_at: float | None = None


class TokenPool:
    """Manages a pool of GitHub tokens with round-robin selection."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self._path = data_file
        self._lock = Lock()
        self._tokens: dict[str, TokenInfo] = {}
        self._robin_index: int = 0
        self._load()

    # ========================================================================
    # Persistence
    # ========================================================================

    def _load(self) -> None:
        """Load token configurations from disk (tokens only, not providers)."""
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for entry in data.get("tokens", []):
                    tid = entry.get("id", uuid4().hex[:12])
                    self._tokens[tid] = TokenInfo(
                        id=tid,
                        alias=entry.get("alias", ""),
                        token=entry.get("token", ""),
                        enabled=entry.get("enabled", True),
                        created_at=entry.get("created_at", time.time()),
                    )
                logger.info("Loaded %d GitHub tokens from %s", len(self._tokens), self._path)
        except Exception:
            logger.warning("Failed to load token pool config", exc_info=True)

    def _save(self) -> None:
        """Persist token configurations to disk (excluding secrets partially)."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            entries = []
            for t in self._tokens.values():
                entries.append({
                    "id": t.id,
                    "alias": t.alias,
                    "token": t.token,
                    "enabled": t.enabled,
                    "created_at": t.created_at,
                })
            self._path.write_text(
                json.dumps({"tokens": entries}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save token pool config")

    # ========================================================================
    # Lifecycle
    # ========================================================================

    async def start_all(self) -> None:
        """Start CopilotProvider instances for all enabled tokens."""
        tasks = []
        for info in self._tokens.values():
            if info.enabled:
                tasks.append(self._start_token(info))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        active = sum(1 for t in self._tokens.values() if t.status == "active")
        logger.info("Token pool started: %d/%d active", active, len(self._tokens))

    async def stop_all(self) -> None:
        """Stop all provider instances gracefully."""
        tasks = []
        for info in self._tokens.values():
            if info.provider is not None:
                tasks.append(self._stop_token(info))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Token pool stopped")

    async def _start_token(self, info: TokenInfo) -> None:
        """Start a single token's provider."""
        try:
            info.status = "pending"
            provider = CopilotProvider(github_token=info.token)
            await provider.start()
            info.provider = provider
            info.status = "active"
            info.error_message = None
            logger.info("Token '%s' (%s) started successfully", info.alias, info.id)
        except Exception as exc:
            info.status = "error"
            info.error_message = str(exc)
            info.provider = None
            logger.error("Failed to start token '%s': %s", info.alias, exc)

    async def _stop_token(self, info: TokenInfo) -> None:
        """Stop a single token's provider."""
        if info.provider is not None:
            try:
                await info.provider.stop()
            except Exception:
                logger.warning("Error stopping token '%s'", info.alias, exc_info=True)
            finally:
                info.provider = None
                info.status = "stopped"

    # ========================================================================
    # Token CRUD
    # ========================================================================

    async def add_token(self, alias: str, token: str, enabled: bool = True) -> TokenInfo:
        """Add a new token to the pool and start it if enabled."""
        tid = uuid4().hex[:12]
        info = TokenInfo(id=tid, alias=alias, token=token, enabled=enabled)
        with self._lock:
            self._tokens[tid] = info
            self._save()
        if enabled:
            await self._start_token(info)
        return info

    async def remove_token(self, token_id: str) -> bool:
        """Remove a token from the pool and stop its provider."""
        with self._lock:
            info = self._tokens.pop(token_id, None)
            if info is None:
                return False
            self._save()
        if info.provider is not None:
            await self._stop_token(info)
        return True

    async def update_token(
        self,
        token_id: str,
        alias: str | None = None,
        enabled: bool | None = None,
        token: str | None = None,
    ) -> bool:
        """Update a token's config. Restarts provider if token value changes."""
        with self._lock:
            info = self._tokens.get(token_id)
            if info is None:
                return False
            if alias is not None:
                info.alias = alias
            need_restart = False
            if token is not None and token != info.token:
                info.token = token
                need_restart = True
            if enabled is not None and enabled != info.enabled:
                info.enabled = enabled
                need_restart = True
            self._save()

        if need_restart:
            await self._stop_token(info)
            if info.enabled:
                await self._start_token(info)

        return True

    async def toggle_token(self, token_id: str, enabled: bool) -> bool:
        """Enable or disable a token."""
        return await self.update_token(token_id, enabled=enabled)

    # ========================================================================
    # Token selection (round-robin)
    # ========================================================================

    def get_active_tokens(self) -> list[TokenInfo]:
        """Return all tokens with active providers."""
        return [t for t in self._tokens.values() if t.status == "active" and t.provider is not None]

    def select_token(self, token_id: str | None = None) -> TokenInfo | None:
        """Select a token for a request.

        If token_id is specified, use that specific token.
        Otherwise, round-robin among active tokens.
        """
        if token_id:
            info = self._tokens.get(token_id)
            if info and info.status == "active" and info.provider is not None:
                return info
            return None

        active = self.get_active_tokens()
        if not active:
            return None

        with self._lock:
            idx = self._robin_index % len(active)
            self._robin_index = idx + 1
            selected = active[idx]
            selected.total_requests += 1
            selected.last_used_at = time.time()
            return selected

    def record_premium_request(self, token_id: str) -> None:
        """Record a premium request for quota tracking."""
        with self._lock:
            info = self._tokens.get(token_id)
            if info:
                info.premium_requests += 1

    # ========================================================================
    # Provider access (for compatibility with existing code)
    # ========================================================================

    def get_provider(self, token_id: str | None = None) -> CopilotProvider | None:
        """Get a provider instance, either by ID or round-robin."""
        info = self.select_token(token_id)
        return info.provider if info else None

    # ========================================================================
    # Status & quota
    # ========================================================================

    def list_tokens(self) -> list[dict]:
        """Return all tokens with their status (token value masked)."""
        result = []
        for t in self._tokens.values():
            masked = t.token[:10] + "..." + t.token[-4:] if len(t.token) > 14 else "***"
            result.append({
                "id": t.id,
                "alias": t.alias,
                "token_preview": masked,
                "enabled": t.enabled,
                "status": t.status,
                "error_message": t.error_message,
                "total_requests": t.total_requests,
                "premium_requests": t.premium_requests,
                "premium_quota_limit": t.premium_quota_limit,
                "premium_quota_used": t.premium_quota_used,
                "premium_quota_reset": t.premium_quota_reset,
                "created_at": t.created_at,
                "last_used_at": t.last_used_at,
            })
        return result

    def get_token_info(self, token_id: str) -> TokenInfo | None:
        """Get a token by ID."""
        return self._tokens.get(token_id)

    def token_count(self) -> int:
        """Total number of tokens in the pool."""
        return len(self._tokens)

    def active_count(self) -> int:
        """Number of active (connected) tokens."""
        return len(self.get_active_tokens())

    async def fetch_quota(self, token_id: str) -> dict | None:
        """Fetch premium request quota via the SDK's account.get_quota() RPC.

        Returns quota snapshots keyed by type (e.g., "premium_interactions",
        "chat", "completions"), each containing entitlement, used, remaining %.
        """
        info = self._tokens.get(token_id)
        if not info:
            return None

        if info.provider is None or info.status != "active":
            return {"error": "Token provider is not active"}

        try:
            snapshots = await info.provider.get_quota()
            # Update cached quota fields from the premium_interactions snapshot
            pi = snapshots.get("premium_interactions") or snapshots.get("chat")
            if pi:
                info.premium_quota_limit = int(pi.get("entitlement_requests", 0))
                info.premium_quota_used = int(pi.get("used_requests", 0))
                info.premium_quota_reset = pi.get("reset_date")
            return {"snapshots": snapshots}
        except Exception as exc:
            logger.warning("Failed to fetch quota for '%s': %s", info.alias, exc)
            return {"error": str(exc)}

    async def fetch_all_quotas(self) -> dict[str, dict]:
        """Fetch quota for all tokens."""
        results = {}
        tasks = []
        for tid in self._tokens:
            tasks.append((tid, self.fetch_quota(tid)))
        for tid, coro in tasks:
            results[tid] = await coro
        return results


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TokenPool | None = None


def get_token_pool() -> TokenPool:
    global _instance
    if _instance is None:
        _instance = TokenPool()
    return _instance
