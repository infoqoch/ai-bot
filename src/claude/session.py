"""Session storage with multi-session support per user."""

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SessionData:
    """Single session data container."""

    def __init__(
        self,
        session_id: str,
        created_at: str,
        last_used: str,
        history: list[str],
        claude_session_id: Optional[str] = None,
    ):
        self.session_id = session_id
        self.created_at = created_at
        self.last_used = last_used
        self.history = history
        self.claude_session_id = claude_session_id  # Claude CLI's session ID

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "last_used": self.last_used,
            "history": self.history,
            "claude_session_id": self.claude_session_id,
        }

    @classmethod
    def from_dict(cls, session_id: str, data: dict) -> "SessionData":
        return cls(
            session_id=session_id,
            created_at=data.get("created_at", ""),
            last_used=data.get("last_used", ""),
            history=data.get("history", []),
            claude_session_id=data.get("claude_session_id"),
        )


class SessionStore:
    """
    Multi-session storage per user.
    
    Data structure:
    {
        "user_id": {
            "current": "session_id",
            "all": {
                "session_id": {
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
                    data = json.load(f)
                return self._migrate_if_needed(data)
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
        return {}
    
    def _migrate_if_needed(self, data: dict) -> dict:
        """Migrate old single-session format to new multi-session format."""
        migrated = {}
        for user_id, user_data in data.items():
            if "all" in user_data and "current" in user_data:
                migrated[user_id] = user_data
            else:
                # Old format migration
                session_id = user_data.get("session_id", "")
                if session_id:
                    migrated[user_id] = {
                        "current": session_id,
                        "all": {
                            session_id: {
                                "created_at": user_data.get("created_at", ""),
                                "last_used": user_data.get("last_used", ""),
                                "history": user_data.get("history", []),
                            }
                        }
                    }
        return migrated
    
    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False, default=str)
    
    def _get_user_data(self, user_id: str) -> Optional[dict]:
        return self._data.get(user_id)
    
    def _get_current_session(self, user_id: str) -> Optional[SessionData]:
        user_data = self._get_user_data(user_id)
        if not user_data:
            return None
        
        current_id = user_data.get("current")
        if not current_id:
            return None
        
        session_dict = user_data.get("all", {}).get(current_id)
        if not session_dict:
            return None
        
        return SessionData.from_dict(current_id, session_dict)
    
    def is_expired(self, user_id: str) -> bool:
        session = self._get_current_session(user_id)
        if not session:
            return True
        
        last_used = datetime.fromisoformat(session.last_used)
        return datetime.now() - last_used > timedelta(hours=self.timeout_hours)
    
    def get_current_session_id(self, user_id: str) -> Optional[str]:
        if self.is_expired(user_id):
            return None
        
        user_data = self._get_user_data(user_id)
        return user_data.get("current") if user_data else None
    
    def get_current_session_info(self, user_id: str) -> str:
        """Return short session ID (first 8 chars)."""
        session_id = self.get_current_session_id(user_id)
        return session_id[:8] if session_id else "없음"
    
    def get_history(self, user_id: str) -> list[str]:
        session = self._get_current_session(user_id)
        return session.history if session else []
    
    def get_history_count(self, user_id: str) -> int:
        return len(self.get_history(user_id))
    
    def create_session(self, user_id: str, first_message: str) -> str:
        """Create a new session and return session ID."""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        if user_id not in self._data:
            self._data[user_id] = {"current": None, "all": {}}
        
        self._data[user_id]["current"] = session_id
        self._data[user_id]["all"][session_id] = {
            "created_at": now,
            "last_used": now,
            "history": [first_message],
        }
        
        self._save()
        return session_id
    
    def add_message(self, user_id: str, message: str) -> None:
        """Add a message to current session history."""
        session = self._get_current_session(user_id)
        if not session:
            return
        
        current_id = self._data[user_id]["current"]
        self._data[user_id]["all"][current_id]["last_used"] = datetime.now().isoformat()
        self._data[user_id]["all"][current_id]["history"].append(message)
        self._save()
    
    def clear_current(self, user_id: str) -> None:
        """Clear current session selection (keeps history)."""
        if user_id in self._data:
            self._data[user_id]["current"] = None
            self._save()
    
    def list_sessions(self, user_id: str) -> list[dict]:
        """List all sessions for a user."""
        user_data = self._get_user_data(user_id)
        if not user_data:
            return []
        
        current_id = user_data.get("current")
        sessions = []
        
        for session_id, data in user_data.get("all", {}).items():
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
        user_data = self._get_user_data(user_id)
        if not user_data:
            return False
        
        for session_id in user_data.get("all", {}).keys():
            if session_id.startswith(session_prefix):
                self._data[user_id]["current"] = session_id
                self._data[user_id]["all"][session_id]["last_used"] = datetime.now().isoformat()
                self._save()
                return True
        
        return False
    
    def get_session_by_prefix(self, user_id: str, prefix: str) -> Optional[dict]:
        """Find session info by ID prefix."""
        user_data = self._get_user_data(user_id)
        if not user_data:
            return None
        
        for session_id, data in user_data.get("all", {}).items():
            if session_id.startswith(prefix):
                return {
                    "session_id": session_id[:8],
                    "full_session_id": session_id,
                    "created_at": data.get("created_at", "")[:19],
                    "last_used": data.get("last_used", "")[:19],
                    "history_count": len(data.get("history", [])),
                }
        
        return None
    
    def get_session_history(self, user_id: str, full_session_id: str) -> list[str]:
        """Get history for a specific session."""
        user_data = self._get_user_data(user_id)
        if not user_data:
            return []
        
        session_data = user_data.get("all", {}).get(full_session_id)
        return session_data.get("history", []) if session_data else []
    
    def get_session_summary(self, user_id: str) -> Optional[dict]:
        """Get current session summary."""
        session = self._get_current_session(user_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "last_used": session.last_used,
            "history": session.history,
            "history_count": len(session.history),
        }

    def get_claude_session_id(self, user_id: str) -> Optional[str]:
        """Get Claude CLI's session ID for current session."""
        session = self._get_current_session(user_id)
        return session.claude_session_id if session else None

    def set_claude_session_id(self, user_id: str, claude_session_id: str) -> None:
        """Store Claude CLI's session ID for current session."""
        user_data = self._get_user_data(user_id)
        if not user_data:
            return

        current_id = user_data.get("current")
        if not current_id:
            return

        self._data[user_id]["all"][current_id]["claude_session_id"] = claude_session_id
        self._save()
