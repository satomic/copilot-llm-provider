"""
API key management service.

Stores multiple API keys with aliases, per-model permissions,
usage limits, and premium request caps.
Persists to a JSON file.
"""

import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/api_keys.json")


@dataclass
class ApiKeyInfo:
    """Information about a managed API key."""

    key: str
    alias: str
    created_at: float
    allowed_models: list[str] | None  # None = all models
    max_requests: int | None  # None = unlimited
    max_premium_requests: int | None  # None = unlimited
    current_requests: int
    current_premium_requests: int
    enabled: bool


class ApiKeyStore:
    """Manages API keys with persistence."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self._path = data_file
        self._lock = Lock()
        self._data: dict = {"keys": {}}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load API key store", exc_info=True)
            self._data = {"keys": {}}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save API key store")

    def create_key(
        self,
        alias: str,
        allowed_models: list[str] | None = None,
        max_requests: int | None = None,
        max_premium_requests: int | None = None,
    ) -> str:
        """Create a new API key. Returns the key string."""
        key = f"sk-{secrets.token_hex(24)}"
        with self._lock:
            self._data["keys"][key] = {
                "alias": alias,
                "created_at": time.time(),
                "allowed_models": allowed_models,
                "max_requests": max_requests,
                "max_premium_requests": max_premium_requests,
                "current_requests": 0,
                "current_premium_requests": 0,
                "enabled": True,
            }
            self._save()
        logger.info("API key created: alias=%s", alias)
        return key

    def validate_key(self, key: str) -> ApiKeyInfo | None:
        """Validate an API key. Returns info or None if invalid."""
        with self._lock:
            entry = self._data["keys"].get(key)
            if not entry or not entry.get("enabled", True):
                return None
            return ApiKeyInfo(
                key=key,
                alias=entry["alias"],
                created_at=entry["created_at"],
                allowed_models=entry.get("allowed_models"),
                max_requests=entry.get("max_requests"),
                max_premium_requests=entry.get("max_premium_requests"),
                current_requests=entry.get("current_requests", 0),
                current_premium_requests=entry.get("current_premium_requests", 0),
                enabled=entry.get("enabled", True),
            )

    def check_model_permission(self, key: str, model: str) -> bool:
        """Check if an API key is allowed to use a specific model."""
        with self._lock:
            entry = self._data["keys"].get(key)
            if not entry:
                return False
            allowed = entry.get("allowed_models")
            if allowed is None:
                return True  # No restrictions
            return model in allowed

    def check_limits(self, key: str, is_premium: bool = False) -> bool:
        """Check if an API key has remaining quota."""
        with self._lock:
            entry = self._data["keys"].get(key)
            if not entry:
                return False
            max_reqs = entry.get("max_requests")
            if max_reqs is not None and entry.get("current_requests", 0) >= max_reqs:
                return False
            if is_premium:
                max_prem = entry.get("max_premium_requests")
                if max_prem is not None and entry.get("current_premium_requests", 0) >= max_prem:
                    return False
            return True

    def record_usage(self, key: str, is_premium: bool = False) -> None:
        """Increment usage counters for a key."""
        with self._lock:
            entry = self._data["keys"].get(key)
            if not entry:
                return
            entry["current_requests"] = entry.get("current_requests", 0) + 1
            if is_premium:
                entry["current_premium_requests"] = entry.get("current_premium_requests", 0) + 1
            self._save()

    def list_keys(self) -> list[dict]:
        """List all API keys with metadata (key partially masked)."""
        with self._lock:
            result = []
            for key, entry in self._data["keys"].items():
                masked = f"{key[:7]}...{key[-4:]}" if len(key) > 11 else "***"
                result.append({
                    "key": key,
                    "key_preview": masked,
                    "alias": entry["alias"],
                    "created_at": entry["created_at"],
                    "allowed_models": entry.get("allowed_models"),
                    "max_requests": entry.get("max_requests"),
                    "max_premium_requests": entry.get("max_premium_requests"),
                    "current_requests": entry.get("current_requests", 0),
                    "current_premium_requests": entry.get("current_premium_requests", 0),
                    "enabled": entry.get("enabled", True),
                })
            return result

    def update_key(
        self,
        key: str,
        alias: str | None = None,
        allowed_models: list[str] | None = ...,  # type: ignore[assignment]
        max_requests: int | None = ...,  # type: ignore[assignment]
        max_premium_requests: int | None = ...,  # type: ignore[assignment]
        enabled: bool | None = None,
    ) -> bool:
        """Update an API key's settings. Returns False if key not found."""
        sentinel = ...
        with self._lock:
            entry = self._data["keys"].get(key)
            if not entry:
                return False
            if alias is not None:
                entry["alias"] = alias
            if allowed_models is not sentinel:
                entry["allowed_models"] = allowed_models
            if max_requests is not sentinel:
                entry["max_requests"] = max_requests
            if max_premium_requests is not sentinel:
                entry["max_premium_requests"] = max_premium_requests
            if enabled is not None:
                entry["enabled"] = enabled
            self._save()
        return True

    def delete_key(self, key: str) -> bool:
        """Delete an API key. Returns False if not found."""
        with self._lock:
            if key not in self._data["keys"]:
                return False
            del self._data["keys"][key]
            self._save()
        logger.info("API key deleted: %s", key[:7])
        return True

    def reset_usage(self, key: str) -> bool:
        """Reset usage counters for a key."""
        with self._lock:
            entry = self._data["keys"].get(key)
            if not entry:
                return False
            entry["current_requests"] = 0
            entry["current_premium_requests"] = 0
            self._save()
        return True

    def has_keys(self) -> bool:
        """Check if any API keys are configured."""
        with self._lock:
            return len(self._data["keys"]) > 0

    def get_alias(self, key: str) -> str | None:
        """Get the alias for an API key."""
        with self._lock:
            entry = self._data["keys"].get(key)
            if entry:
                return entry.get("alias")
            return None


_instance: ApiKeyStore | None = None


def get_api_key_store() -> ApiKeyStore:
    global _instance
    if _instance is None:
        _instance = ApiKeyStore()
    return _instance
