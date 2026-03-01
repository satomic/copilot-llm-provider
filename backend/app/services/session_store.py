"""
Session persistence service.

Records every chat completion request/response as a JSON file
in data/sessions/ for audit and review purposes.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path("data/sessions")


@dataclass
class SessionRecord:
    """A recorded chat session."""

    id: str = field(default_factory=lambda: uuid4().hex[:16])
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    api_format: str = "openai"  # "openai" or "anthropic"
    messages: list[dict] = field(default_factory=list)
    response_content: str = ""
    stream: bool = False
    duration_ms: float = 0
    status: str = "ok"  # "ok" or "error"
    error_message: str | None = None
    client_ip: str | None = None
    api_key_alias: str | None = None
    github_token_alias: str | None = None


class SessionStore:
    """Persists session records as JSON files."""

    def __init__(self, sessions_dir: Path = SESSIONS_DIR) -> None:
        self._dir = sessions_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, record: SessionRecord) -> str:
        path = self._dir / f"{record.id}.json"
        try:
            data = asdict(record)
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Session saved: %s", record.id)
        except Exception:
            logger.exception("Failed to save session %s", record.id)
        return record.id

    def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
        model: str | None = None,
        api_key_alias: str | None = None,
        github_token_alias: str | None = None,
    ) -> list[dict]:
        files = sorted(self._dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        results = []
        skipped = 0
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                # Apply filters
                if model and data.get("model", "") != model:
                    continue
                if api_key_alias and data.get("api_key_alias") != api_key_alias:
                    continue
                if github_token_alias and data.get("github_token_alias") != github_token_alias:
                    continue
                # Pagination after filtering
                skipped += 1
                if skipped <= offset:
                    continue
                if len(results) >= limit:
                    break
                # Extract first user message
                messages = data.get("messages", [])
                first_msg = ""
                for m in messages:
                    if m.get("role") == "user":
                        first_msg = (m.get("content", "") or "")[:120]
                        break
                results.append({
                    "id": data.get("id", f.stem),
                    "timestamp": data.get("timestamp", 0),
                    "model": data.get("model", ""),
                    "api_format": data.get("api_format", "openai"),
                    "stream": data.get("stream", False),
                    "duration_ms": data.get("duration_ms", 0),
                    "status": data.get("status", "ok"),
                    "message_count": len(messages),
                    "response_preview": (data.get("response_content", "") or "")[:100],
                    "api_key_alias": data.get("api_key_alias"),
                    "github_token_alias": data.get("github_token_alias"),
                    "first_message": first_msg,
                })
            except Exception:
                logger.warning("Failed to read session file %s", f, exc_info=True)
        return results

    def update(self, session_id: str, data: dict) -> None:
        """Update an existing session file in-place."""
        path = self._dir / f"{session_id}.json"
        try:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Session updated: %s", session_id)
        except Exception:
            logger.exception("Failed to update session %s", session_id)

    def get_session(self, session_id: str) -> dict | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to read session %s", session_id)
            return None

    def delete(self, session_id: str) -> bool:
        """Delete a single session file. Returns True if deleted."""
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return False
        try:
            path.unlink()
            logger.debug("Session deleted: %s", session_id)
            return True
        except Exception:
            logger.exception("Failed to delete session %s", session_id)
            return False

    def delete_batch(self, session_ids: list[str]) -> int:
        """Delete multiple sessions. Returns the count actually deleted."""
        deleted = 0
        for sid in session_ids:
            if self.delete(sid):
                deleted += 1
        return deleted

    def get_total_count(
        self,
        model: str | None = None,
        api_key_alias: str | None = None,
        github_token_alias: str | None = None,
    ) -> int:
        if not model and not api_key_alias and not github_token_alias:
            return len(list(self._dir.glob("*.json")))
        count = 0
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if model and data.get("model", "") != model:
                    continue
                if api_key_alias and data.get("api_key_alias") != api_key_alias:
                    continue
                if github_token_alias and data.get("github_token_alias") != github_token_alias:
                    continue
                count += 1
            except Exception:
                pass
        return count

    def get_filter_options(self) -> dict:
        """Return distinct models, API key aliases, and GitHub token aliases for filtering."""
        models: set[str] = set()
        aliases: set[str] = set()
        token_aliases: set[str] = set()
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                m = data.get("model", "")
                if m:
                    models.add(m)
                a = data.get("api_key_alias")
                if a:
                    aliases.add(a)
                ta = data.get("github_token_alias")
                if ta:
                    token_aliases.add(ta)
            except Exception:
                pass
        return {
            "models": sorted(models),
            "aliases": sorted(aliases),
            "token_aliases": sorted(token_aliases),
        }


_instance: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _instance
    if _instance is None:
        _instance = SessionStore()
    return _instance
