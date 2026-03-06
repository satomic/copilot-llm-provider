"""
Runtime configuration manager.

Stores configuration that can be changed at runtime via admin API endpoints.
Persists to a JSON file so settings survive server restarts.
"""

import json
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "runtime_config.json"


class RuntimeConfig:
    """Thread-safe runtime configuration backed by a JSON file."""

    def __init__(self, config_path: Path = CONFIG_FILE) -> None:
        self._path = config_path
        self._lock = Lock()
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                logger.info("Loaded runtime config from %s", self._path)
            else:
                self._data = {}
        except Exception:
            logger.warning("Failed to load runtime config", exc_info=True)
            self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save runtime config")

    @property
    def api_key(self) -> str | None:
        with self._lock:
            return self._data.get("api_key")

    @api_key.setter
    def api_key(self, value: str | None) -> None:
        with self._lock:
            if value:
                self._data["api_key"] = value
            else:
                self._data.pop("api_key", None)
            self._save()


_instance: RuntimeConfig | None = None


def get_runtime_config() -> RuntimeConfig:
    global _instance
    if _instance is None:
        _instance = RuntimeConfig()
    return _instance
