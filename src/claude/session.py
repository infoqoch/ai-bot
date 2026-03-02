"""Session storage - Claude session_id as primary key."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class SessionData(TypedDict):
    """Type definition for session data structure."""

    created_at: str
    last_used: str
    history: list[str]


class SessionStore:
    """
    Session storage using Claude's session_id as primary key.

    Data structure:
    {
        "user_id": {
            "current": "claude_session_id",
            "sessions": {
                "claude_session_id": {
                    "created_at": "...",
                    "last_used": "...",
                    "history": [...]
                }
            }
        }
    }
    """

    def __init__(self, file_path: Path, timeout_hours: int = 24):
        self.file_path = file_path
        self.timeout_hours = timeout_hours
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
        return {}

    def _save(self) -> bool:
        """Save session data. Returns True on success."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            # atomic write: 임시 파일에 쓴 후 이동
            temp_file = self.file_path.with_suffix('.tmp')
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False, default=str)
            temp_file.replace(self.file_path)
            return True
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
            return False

    def _ensure_user(self, user_id: str) -> dict:
        """Ensure user data structure exists."""
        if user_id not in self._data:
            self._data[user_id] = {"current": None, "sessions": {}}
        return self._data[user_id]

    def get_current_session_id(self, user_id: str) -> Optional[str]:
        """Get current session_id for user (None if expired or not exists)."""
        user_data = self._data.get(user_id)
        if not user_data:
            return None

        session_id = user_data.get("current")
        if not session_id:
            return None

        session = user_data.get("sessions", {}).get(session_id)
        if not session:
            return None

        # Check expiration
        try:
            last_used = datetime.fromisoformat(session["last_used"])
        except (ValueError, KeyError, TypeError):
            logger.warning(f"Invalid timestamp for session {session_id[:8]}")
            return None

        if datetime.now() - last_used > timedelta(hours=self.timeout_hours):
            logger.info(f"[{user_id}] Session expired: {session_id[:8]}")
            return None

        return session_id

    def create_session(self, user_id: str, session_id: str, first_message: str) -> None:
        """Create a new session with Claude's session_id."""
        user_data = self._ensure_user(user_id)
        now = datetime.now().isoformat()

        user_data["current"] = session_id
        user_data["sessions"][session_id] = {
            "created_at": now,
            "last_used": now,
            "history": [first_message],
        }

        self._save()
        logger.info(f"[{user_id}] Created session: {session_id[:8]}")

    def add_message(self, user_id: str, session_id: str, message: str) -> None:
        """Add a message to specific session (not current!)."""
        user_data = self._data.get(user_id)
        if not user_data:
            return

        session = user_data.get("sessions", {}).get(session_id)
        if not session:
            return

        session["last_used"] = datetime.now().isoformat()
        session["history"].append(message)
        self._save()

    def set_current(self, user_id: str, session_id: str) -> None:
        """Set current session for user."""
        user_data = self._ensure_user(user_id)
        if session_id in user_data.get("sessions", {}):
            user_data["current"] = session_id
            user_data["sessions"][session_id]["last_used"] = datetime.now().isoformat()
            self._save()

    def clear_current(self, user_id: str) -> None:
        """Clear current session selection."""
        if user_id in self._data:
            self._data[user_id]["current"] = None
            self._save()

    def get_session_info(self, user_id: str, session_id: str) -> str:
        """Return short session ID (first 8 chars)."""
        return session_id[:8] if session_id else "없음"

    def get_history_count(self, user_id: str, session_id: str) -> int:
        """Get history count for specific session."""
        user_data = self._data.get(user_id)
        if not user_data:
            return 0

        session = user_data.get("sessions", {}).get(session_id)
        return len(session.get("history", [])) if session else 0

    def list_sessions(self, user_id: str) -> list[dict]:
        """List all sessions for a user."""
        user_data = self._data.get(user_id)
        if not user_data:
            return []

        current_id = user_data.get("current")
        sessions = []

        for session_id, data in user_data.get("sessions", {}).items():
            sessions.append({
                "session_id": session_id[:8],
                "full_session_id": session_id,
                "created_at": data.get("created_at", "")[:19],
                "last_used": data.get("last_used", "")[:19],
                "history_count": len(data.get("history", [])),
                "is_current": session_id == current_id,
            })

        sessions.sort(key=lambda x: x["last_used"], reverse=True)
        return sessions

    def switch_session(self, user_id: str, session_prefix: str) -> bool:
        """Switch to a session by ID prefix."""
        user_data = self._data.get(user_id)
        if not user_data:
            return False

        for session_id in user_data.get("sessions", {}).keys():
            if session_id.startswith(session_prefix):
                self.set_current(user_id, session_id)
                return True

        return False

    def get_session_by_prefix(self, user_id: str, prefix: str) -> Optional[dict]:
        """Find session info by ID prefix."""
        user_data = self._data.get(user_id)
        if not user_data:
            return None

        for session_id, data in user_data.get("sessions", {}).items():
            if session_id.startswith(prefix):
                return {
                    "session_id": session_id[:8],
                    "full_session_id": session_id,
                    "created_at": data.get("created_at", "")[:19],
                    "last_used": data.get("last_used", "")[:19],
                    "history_count": len(data.get("history", [])),
                }

        return None

    def get_session_history(self, user_id: str, session_id: str) -> list[str]:
        """Get history for a specific session."""
        user_data = self._data.get(user_id)
        if not user_data:
            return []

        session = user_data.get("sessions", {}).get(session_id)
        return session.get("history", []) if session else []
