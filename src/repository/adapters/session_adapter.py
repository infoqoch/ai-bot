"""Session store adapter for backward compatibility."""

from datetime import datetime, timedelta
from typing import Any, Optional, TypedDict

from ..repository import Repository, SessionData, HistoryEntry


class HistoryEntryDict(TypedDict):
    """History entry as dict (for backward compatibility)."""
    message: str
    timestamp: str
    processed: bool
    processor: Optional[str]


class SessionStoreAdapter:
    """Adapter that provides SessionStore-compatible interface over Repository.

    This adapter maintains the same API as the original SessionStore class
    to ensure backward compatibility with existing code.
    """

    def __init__(self, repo: Repository, session_timeout_hours: int = 24):
        self._repo = repo
        self._session_timeout_hours = session_timeout_hours

    def _is_session_expired(self, last_used: str) -> bool:
        """Check if session is expired based on last_used timestamp."""
        try:
            last_used_dt = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
            # Handle timezone-naive datetime
            if last_used_dt.tzinfo is None:
                last_used_dt = last_used_dt.replace(tzinfo=None)
                now = datetime.utcnow()
            else:
                now = datetime.now(last_used_dt.tzinfo)
            return (now - last_used_dt) > timedelta(hours=self._session_timeout_hours)
        except (ValueError, TypeError):
            return False

    def get_current_session_id(self, user_id: str) -> Optional[str]:
        """Get current session ID with expiration check."""
        session_id = self._repo.get_current_session_id(user_id)
        if not session_id:
            return None

        session = self._repo.get_session(session_id)
        if not session:
            return None

        # Check if deleted
        if session.deleted:
            return None

        # Check if expired
        if self._is_session_expired(session.last_used):
            return None

        return session_id

    def get_previous_session_id(self, user_id: str) -> Optional[str]:
        """Get previous session ID."""
        return self._repo.get_previous_session_id(user_id)

    def create_session(
        self,
        user_id: str,
        session_id: str,
        first_message: str = "",
        model: str = "sonnet",
        name: Optional[str] = None,
        processor: str = "claude",
        workspace_path: Optional[str] = None
    ) -> None:
        """Create new session and switch to it.

        Args:
            user_id: User ID
            session_id: Claude session ID
            first_message: First message (for history)
            model: Model name (opus/sonnet/haiku)
            name: Session display name
            processor: Message processor (claude/plugin:name)
            workspace_path: Workspace path for workspace sessions
        """
        self._repo.create_session(
            user_id=user_id,
            session_id=session_id,
            model=model,
            name=name,
            workspace_path=workspace_path,
            switch_to=True
        )

        # Add first message to history if provided
        if first_message:
            self._repo.add_message(session_id, first_message, processed=True, processor=processor)

    def create_session_without_switch(
        self,
        user_id: str,
        session_id: str,
        first_message: str = "",
        model: str = "sonnet",
        name: Optional[str] = None,
        processor: str = "claude",
        workspace_path: Optional[str] = None
    ) -> None:
        """Create session without switching to it."""
        self._repo.create_session_without_switch(
            user_id=user_id,
            session_id=session_id,
            model=model,
            name=name,
            workspace_path=workspace_path
        )

        # Add first message to history if provided
        if first_message:
            self._repo.add_message(session_id, first_message, processed=True, processor=processor)

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Get session data as dict."""
        session = self._repo.get_session(session_id)
        if not session:
            return None

        # Get history
        history = self._repo.get_session_history_entries(session_id)

        return {
            "created_at": session.created_at,
            "last_used": session.last_used,
            "history": [h.to_dict() for h in history],
            "model": session.model,
            "name": session.name,
            "workspace_path": session.workspace_path,
            "deleted": session.deleted,
        }

    def get_session_model(self, user_id: str, session_id: str) -> Optional[str]:
        """Get model for session."""
        return self._repo.get_session_model(session_id)

    def set_session_model(self, user_id: str, session_id: str, model: str) -> bool:
        """Set/update session model.

        Args:
            user_id: User ID (for compatibility, not used)
            session_id: Session ID
            model: New model name (opus/sonnet/haiku)

        Returns:
            True if successful, False otherwise
        """
        return self._repo.update_session_model(session_id, model)

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete session (soft delete).

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            True if successful, False otherwise
        """
        result = self._repo.soft_delete_session(session_id)
        if result:
            current = self._repo.get_current_session_id(user_id)
            if current == session_id:
                previous = self._repo.get_previous_session_id(user_id)
                self._repo.update_user_current_session(user_id, previous, None)
        return result

    def add_message(
        self,
        user_id_or_session_id: str,
        session_id_or_message: str,
        message_or_processed: str | bool = "",
        processed: bool = False,
        processor: Optional[str] = None
    ) -> None:
        """Add message to session history.

        Supports multiple call signatures for backward compatibility:
        - add_message(session_id, message)
        - add_message(session_id, message, processed=True, processor="claude")
        - add_message(user_id, session_id, message, processor=...)
        """
        # Detect which signature is being used
        if isinstance(message_or_processed, bool):
            # Old signature: add_message(session_id, message, processed=..., processor=...)
            session_id = user_id_or_session_id
            message = session_id_or_message
            actual_processed = message_or_processed
        elif message_or_processed == "":
            # Simple signature: add_message(session_id, message)
            session_id = user_id_or_session_id
            message = session_id_or_message
            actual_processed = processed
        else:
            # New signature: add_message(user_id, session_id, message, processor=...)
            session_id = session_id_or_message
            message = str(message_or_processed)
            actual_processed = True  # Assume processed when called from handlers

        self._repo.add_message(session_id, message, actual_processed, processor)

    def get_session_history(
        self,
        user_id_or_session_id: str,
        session_id_or_limit: Optional[str | int] = None,
        limit: Optional[int] = None
    ) -> list[str]:
        """Get session history as list of messages (legacy format).

        Supports two call signatures for backward compatibility:
        - get_session_history(session_id) or get_session_history(session_id, limit)
        - get_session_history(user_id, session_id) or get_session_history(user_id, session_id, limit)
        """
        # Detect which signature is being used
        if session_id_or_limit is None:
            # Single arg: get_session_history(session_id)
            return self._repo.get_session_history(user_id_or_session_id, None)
        elif isinstance(session_id_or_limit, int):
            # Two args with int: get_session_history(session_id, limit)
            return self._repo.get_session_history(user_id_or_session_id, session_id_or_limit)
        else:
            # Two or three args with string: get_session_history(user_id, session_id, [limit])
            return self._repo.get_session_history(session_id_or_limit, limit)

    def get_session_history_entries(
        self,
        user_id: str,
        session_id: str,
        limit: Optional[int] = None
    ) -> list[HistoryEntryDict]:
        """Get session history as list of dicts."""
        entries = self._repo.get_session_history_entries(session_id, limit)
        return [
            {
                "message": e.message,
                "timestamp": e.timestamp,
                "processed": e.processed,
                "processor": e.processor,
            }
            for e in entries
        ]

    def update_session_name(self, session_id: str, name: str) -> bool:
        """Update session name."""
        return self._repo.update_session_name(session_id, name)

    def soft_delete_session(self, user_id: str, session_id: str) -> bool:
        """Soft delete session.

        If deleting current session, switch to previous or None.
        """
        result = self._repo.soft_delete_session(session_id)
        if result:
            current = self._repo.get_current_session_id(user_id)
            if current == session_id:
                previous = self._repo.get_previous_session_id(user_id)
                self._repo.update_user_current_session(user_id, previous, None)
        return result

    def hard_delete_session(self, user_id: str, session_id: str) -> bool:
        """Hard delete session."""
        result = self._repo.hard_delete_session(session_id)
        if result:
            current = self._repo.get_current_session_id(user_id)
            if current == session_id:
                previous = self._repo.get_previous_session_id(user_id)
                self._repo.update_user_current_session(user_id, previous, None)
        return result

    def restore_session(self, session_id: str) -> bool:
        """Restore soft-deleted session."""
        return self._repo.restore_session(session_id)

    def list_sessions(
        self,
        user_id: str,
        include_deleted: bool = False,
        limit: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """List sessions for user."""
        sessions = self._repo.list_sessions(user_id, include_deleted, limit)
        current_id = self._repo.get_current_session_id(user_id)

        result = []
        for s in sessions:
            history = self._repo.get_session_history_entries(s.id)
            result.append({
                "id": s.id,
                "full_session_id": s.id,  # 원본 코드 호환
                "session_id": s.id[:8],   # 원본 코드 호환 (short ID)
                "created_at": s.created_at,
                "last_used": s.last_used,
                "history": [h.to_dict() for h in history],
                "model": s.model,
                "name": s.name,
                "workspace_path": s.workspace_path,
                "deleted": s.deleted,
                "is_current": s.id == current_id,
            })
        return result

    def switch_session(self, user_id: str, session_id: str) -> bool:
        """Switch to a different session."""
        return self._repo.switch_session(user_id, session_id)

    def is_workspace_session(self, session_id: str) -> bool:
        """Check if session is a workspace session."""
        return self._repo.is_workspace_session(session_id)

    def get_session_workspace_path(self, user_id: str, session_id: str) -> Optional[str]:
        """Get workspace path for session."""
        return self._repo.get_session_workspace_path(session_id)

    def get_all_sessions_summary(self, user_id: str) -> str:
        """Get all sessions summary for manager display."""
        sessions = self._repo.list_sessions(user_id, include_deleted=False)
        current_id = self._repo.get_current_session_id(user_id)

        if not sessions:
            return "세션이 없습니다."

        lines = []
        for s in sessions:
            # Emoji indicators
            emoji = "📍" if s.id == current_id else "💬"
            if s.workspace_path:
                emoji = "📂" if s.id == current_id else "🗂"

            # Session name or ID
            display_name = s.name or s.id[:8]

            # Model badge
            model_badge = {"opus": "🟣", "sonnet": "🔵", "haiku": "🟢"}.get(s.model, "⚪")

            # History count
            history = self._repo.get_session_history_entries(s.id)
            msg_count = len(history)

            lines.append(f"{emoji} {model_badge} <b>{display_name}</b> ({msg_count}개)")

        return "\n".join(lines)

    def clear_session_history(self, session_id: str) -> int:
        """Clear session history."""
        return self._repo.clear_session_history(session_id)

    def update_last_used(self, session_id: str) -> None:
        """Update session last_used timestamp."""
        self._repo.update_session_last_used(session_id)

    def get_session_info(self, user_id: str, session_id: str) -> str:
        """Return short session ID with optional name.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Format: "abc12345 (세션이름)" or "abc12345" or "없음"
        """
        if not session_id:
            return "없음"

        session = self._repo.get_session(session_id)
        if not session:
            return session_id[:8]

        short_id = session_id[:8]
        if session.name:
            return f"{short_id} ({session.name})"
        return short_id

    def get_history_count(self, user_id: str, session_id: str) -> int:
        """Get message count in session history.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Number of messages in history
        """
        if not session_id:
            return 0

        history = self._repo.get_session_history_entries(session_id)
        return len(history)

    def get_session_name(self, user_id: str, session_id: str) -> str:
        """Get session name.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Session name or empty string if not found
        """
        if not session_id:
            return ""

        session = self._repo.get_session(session_id)
        if not session:
            return ""

        return session.name or ""

    def get_session_by_prefix(
        self,
        user_id: str,
        prefix: str,
        include_deleted: bool = False
    ) -> Optional[dict[str, Any]]:
        """Find session info by ID prefix.

        Args:
            user_id: User ID
            prefix: Session ID prefix to match
            include_deleted: If True, also search in soft-deleted sessions

        Returns:
            Session info dict or None if not found
        """
        sessions = self._repo.list_sessions(user_id, include_deleted=include_deleted)

        for s in sessions:
            if s.id.startswith(prefix):
                history = self._repo.get_session_history_entries(s.id)
                return {
                    "session_id": s.id[:8],
                    "full_session_id": s.id,
                    "created_at": s.created_at[:19] if s.created_at else "",
                    "last_used": s.last_used[:19] if s.last_used else "",
                    "history_count": len(history),
                    "name": s.name or "",
                    "model": s.model or "sonnet",
                    "project_path": s.workspace_path or "",
                    "workspace_path": s.workspace_path or "",
                    "deleted": s.deleted,
                }

        return None

    def set_previous_session_id(self, user_id: str, session_id: Optional[str]) -> None:
        """Store previous session ID for /back command.

        Args:
            user_id: User ID
            session_id: Session ID to store as previous (or None to clear)
        """
        current = self._repo.get_current_session_id(user_id)
        self._repo.update_user_current_session(user_id, current, session_id)

    def set_current(self, user_id: str, session_id: Optional[str]) -> None:
        """Set current session ID.

        Args:
            user_id: User ID
            session_id: Session ID to set as current (or None to clear)
        """
        previous = self._repo.get_current_session_id(user_id)
        self._repo.update_user_current_session(user_id, session_id, previous)

    def rename_session(self, user_id: str, session_id: str, new_name: str) -> bool:
        """Rename a session.

        Args:
            user_id: User ID
            session_id: Session ID
            new_name: New name for the session

        Returns:
            True if successful, False otherwise
        """
        return self._repo.update_session_name(session_id, new_name)
