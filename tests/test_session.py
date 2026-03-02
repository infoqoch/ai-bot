"""Tests for session storage."""

import json
import tempfile
from pathlib import Path

import pytest

from src.claude.session import SessionStore


@pytest.fixture
def temp_session_file():
    """Create a temporary session file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({}, f)
        return Path(f.name)


@pytest.fixture
def session_store(temp_session_file):
    """Create a session store with temp file."""
    return SessionStore(file_path=temp_session_file, timeout_hours=24)


class TestSessionStore:
    def test_create_session(self, session_store):
        user_id = "test_user"
        session_id = session_store.create_session(user_id, "Hello")
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID length
        assert session_store.get_current_session_id(user_id) == session_id
    
    def test_add_message(self, session_store):
        user_id = "test_user"
        session_store.create_session(user_id, "First message")
        session_store.add_message(user_id, "Second message")
        
        history = session_store.get_history(user_id)
        assert len(history) == 2
        assert history[0] == "First message"
        assert history[1] == "Second message"
    
    def test_list_sessions(self, session_store):
        user_id = "test_user"
        
        # Create multiple sessions
        session_store.create_session(user_id, "Session 1")
        session_store.clear_current(user_id)
        session_store.create_session(user_id, "Session 2")
        
        sessions = session_store.list_sessions(user_id)
        assert len(sessions) == 2
    
    def test_switch_session(self, session_store):
        user_id = "test_user"
        
        # Create first session
        first_id = session_store.create_session(user_id, "First")
        session_store.clear_current(user_id)
        
        # Create second session
        second_id = session_store.create_session(user_id, "Second")
        
        # Switch back to first
        assert session_store.switch_session(user_id, first_id[:8])
        assert session_store.get_current_session_id(user_id) == first_id
    
    def test_get_session_info(self, session_store):
        user_id = "test_user"
        
        # No session
        assert session_store.get_current_session_info(user_id) == "없음"
        
        # With session
        session_id = session_store.create_session(user_id, "Test")
        assert session_store.get_current_session_info(user_id) == session_id[:8]
    
    def test_migration_old_format(self, temp_session_file):
        # Write old format data
        old_data = {
            "user123": {
                "session_id": "abc-123-def",
                "created_at": "2024-01-01T00:00:00",
                "last_used": "2024-01-01T00:00:00",
                "history": ["test message"]
            }
        }
        with open(temp_session_file, 'w') as f:
            json.dump(old_data, f)
        
        # Load with new store - should migrate
        store = SessionStore(file_path=temp_session_file, timeout_hours=24)
        
        sessions = store.list_sessions("user123")
        assert len(sessions) == 1
        assert sessions[0]["full_session_id"] == "abc-123-def"
