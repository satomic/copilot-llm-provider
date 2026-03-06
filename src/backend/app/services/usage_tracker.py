"""
Usage tracking service.

Tracks per-model request counts and categorizes models into three tiers
based on the SDK billing multiplier:
  - Free:     multiplier == 0
  - Standard: 0 < multiplier <= 1
  - Premium:  multiplier > 1

Persists stats to a JSON file.
"""

import json
import logging
import time
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/usage_stats.json")


def _tier_of(multiplier: float) -> str:
    """Determine tier from billing multiplier.

    multiplier > 0 → premium (costs requests)
    multiplier == 0 → free
    """
    if multiplier > 0:
        return "premium"
    return "free"


class UsageTracker:
    """Tracks API usage per model with persistence."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self._path = data_file
        self._lock = Lock()
        self._data: dict = {"models": {}, "daily": {}, "by_alias": {}}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load usage stats", exc_info=True)
            self._data = {"models": {}, "daily": {}}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save usage stats")

    def record_request(
        self,
        model: str,
        api_format: str = "openai",
        stream: bool = False,
        is_premium: bool | None = None,
        multiplier: float | None = None,
        api_key_alias: str | None = None,
        github_token_alias: str | None = None,
    ) -> None:
        """Record a request.

        ``is_premium`` comes from the SDK billing multiplier.
        ``multiplier`` is the raw billing multiplier value from the SDK.
        ``api_key_alias`` is the alias of the API key used (if managed).
        ``github_token_alias`` is the alias of the GitHub token used.
        """
        today = time.strftime("%Y-%m-%d")
        with self._lock:
            # Per-model lifetime stats
            if model not in self._data["models"]:
                self._data["models"][model] = {
                    "total_requests": 0,
                    "stream_requests": 0,
                    "is_premium": is_premium if is_premium is not None else True,
                    "multiplier": multiplier if multiplier is not None else 1.0,
                    "last_used": "",
                }
            entry = self._data["models"][model]
            entry["total_requests"] += 1
            if stream:
                entry["stream_requests"] += 1
            entry["last_used"] = today
            # Update fields if explicitly provided
            if is_premium is not None:
                entry["is_premium"] = is_premium
            if multiplier is not None:
                entry["multiplier"] = multiplier

            # Determine tier from multiplier
            mult = entry.get("multiplier", 1.0)
            tier = _tier_of(mult)

            # Daily stats (3-tier breakdown)
            if today not in self._data["daily"]:
                self._data["daily"][today] = {
                    "total": 0,
                    "premium": 0,
                    "free": 0,
                }
            day = self._data["daily"][today]
            day["total"] += 1
            day[tier] += 1

            # Per-alias stats (API key)
            if api_key_alias:
                if "by_alias" not in self._data:
                    self._data["by_alias"] = {}
                alias_data = self._data["by_alias"]
                if api_key_alias not in alias_data:
                    alias_data[api_key_alias] = {
                        "total_requests": 0,
                        "premium_requests": 0,
                        "models": {},
                    }
                alias_entry = alias_data[api_key_alias]
                alias_entry["total_requests"] += 1
                if tier == "premium":
                    alias_entry["premium_requests"] += 1
                if model not in alias_entry["models"]:
                    alias_entry["models"][model] = 0
                alias_entry["models"][model] += 1

            # Per-token stats (GitHub token)
            if github_token_alias:
                if "by_token" not in self._data:
                    self._data["by_token"] = {}
                token_data = self._data["by_token"]
                if github_token_alias not in token_data:
                    token_data[github_token_alias] = {
                        "total_requests": 0,
                        "premium_requests": 0,
                        "models": {},
                    }
                token_entry = token_data[github_token_alias]
                token_entry["total_requests"] += 1
                if tier == "premium":
                    token_entry["premium_requests"] += 1
                if model not in token_entry["models"]:
                    token_entry["models"][model] = 0
                token_entry["models"][model] += 1

            self._save()

    def get_stats(self) -> dict:
        with self._lock:
            models = self._data.get("models", {})
            daily = self._data.get("daily", {})

            total_requests = sum(m["total_requests"] for m in models.values())
            premium_requests = sum(
                m["total_requests"]
                for m in models.values()
                if m.get("multiplier", 1.0) > 0
            )
            free_requests = total_requests - premium_requests

            # Last 7 days — merge legacy "standard" into "free"
            recent_days = sorted(daily.keys(), reverse=True)[:7]
            recent_daily = {}
            for d in recent_days:
                entry = daily[d]
                recent_daily[d] = {
                    "total": entry.get("total", 0),
                    "premium": entry.get("premium", 0),
                    "free": entry.get("free", 0) + entry.get("standard", 0),
                }

            by_alias = self._data.get("by_alias", {})
            by_token = self._data.get("by_token", {})

            return {
                "total_requests": total_requests,
                "premium_requests": premium_requests,
                "free_requests": free_requests,
                "models": models,
                "recent_daily": recent_daily,
                "by_alias": by_alias,
                "by_token": by_token,
            }


_instance: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    global _instance
    if _instance is None:
        _instance = UsageTracker()
    return _instance
