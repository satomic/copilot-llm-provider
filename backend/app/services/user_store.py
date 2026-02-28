"""
User account management service.

Stores user accounts with hashed passwords in a JSON file.
Uses PBKDF2-SHA256 for password hashing (no external dependencies).
"""

import hashlib
import json
import logging
import os
import secrets
import time
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/users.json")


def _hash_password(password: str, salt: str) -> str:
    """Hash a password with PBKDF2-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex()


class UserStore:
    """Manages user accounts with persistence."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self._path = data_file
        self._lock = Lock()
        self._data: dict = {"users": {}, "sessions": {}}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                if "sessions" not in self._data:
                    self._data["sessions"] = {}
        except Exception:
            logger.warning("Failed to load user store", exc_info=True)
            self._data = {"users": {}, "sessions": {}}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save user store")

    def has_users(self) -> bool:
        """Check if any user accounts exist."""
        with self._lock:
            return len(self._data["users"]) > 0

    def register(self, username: str, password: str) -> bool:
        """Register a new user. Returns False if username already taken."""
        with self._lock:
            if username in self._data["users"]:
                return False
            salt = os.urandom(32).hex()
            self._data["users"][username] = {
                "password_hash": _hash_password(password, salt),
                "salt": salt,
                "created_at": time.time(),
            }
            self._save()
            logger.info("User registered: %s", username)
            return True

    def authenticate(self, username: str, password: str) -> bool:
        """Verify username and password."""
        with self._lock:
            user = self._data["users"].get(username)
            if not user:
                return False
            expected = _hash_password(password, user["salt"])
            return secrets.compare_digest(expected, user["password_hash"])

    def create_session(self, username: str) -> str:
        """Create a login session token for a user."""
        token = f"sess-{secrets.token_hex(24)}"
        with self._lock:
            self._data["sessions"][token] = {
                "username": username,
                "created_at": time.time(),
            }
            self._save()
        return token

    def validate_session(self, token: str) -> str | None:
        """Validate a session token. Returns username or None."""
        with self._lock:
            session = self._data["sessions"].get(token)
            if session:
                return session["username"]
            return None

    def invalidate_session(self, token: str) -> None:
        """Remove a session token."""
        with self._lock:
            self._data["sessions"].pop(token, None)
            self._save()


_instance: UserStore | None = None


def get_user_store() -> UserStore:
    global _instance
    if _instance is None:
        _instance = UserStore()
    return _instance
