"""세션 저장소 테스트.

SessionStore 클래스의 핵심 기능 검증:
- 세션 생성 및 저장
- 메시지 추가
- 세션 목록 및 전환
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.claude.session import SessionStore


@pytest.fixture
def temp_session_file():
    """임시 세션 파일 생성."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({}, f)
        return Path(f.name)


@pytest.fixture
def session_store(temp_session_file):
    """테스트용 세션 저장소 생성."""
    return SessionStore(file_path=temp_session_file, timeout_hours=24)


class TestSessionStore:
    """SessionStore 단위 테스트."""

    def test_create_session(self, session_store):
        """세션 생성 확인."""
        user_id = "123"
        session_id = "claude-session-abc"

        session_store.create_session(user_id, session_id, "첫 메시지")

        current = session_store.get_current_session_id(user_id)
        assert current == session_id

    def test_add_message(self, session_store):
        """메시지 추가 확인."""
        user_id = "123"
        session_id = "claude-session-abc"

        session_store.create_session(user_id, session_id, "첫 메시지")
        session_store.add_message(user_id, session_id, "두 번째 메시지")

        history = session_store.get_session_history(user_id, session_id)
        assert len(history) == 2
        assert history[0] == "첫 메시지"
        assert history[1] == "두 번째 메시지"

    def test_list_sessions(self, session_store):
        """세션 목록 확인."""
        user_id = "123"

        session_store.create_session(user_id, "session-1", "메시지1")
        session_store.create_session(user_id, "session-2", "메시지2")

        sessions = session_store.list_sessions(user_id)
        assert len(sessions) == 2

    def test_switch_session(self, session_store):
        """세션 전환 확인."""
        user_id = "123"

        session_store.create_session(user_id, "session-1-abc", "메시지1")
        session_store.create_session(user_id, "session-2-def", "메시지2")

        # session-2가 current
        assert session_store.get_current_session_id(user_id) == "session-2-def"

        # session-1로 전환
        result = session_store.switch_session(user_id, "session-1")
        assert result is True
        assert session_store.get_current_session_id(user_id) == "session-1-abc"

    def test_get_session_info(self, session_store):
        """세션 정보 확인."""
        user_id = "123"
        session_id = "abcd1234-5678-90ab-cdef-1234567890ab"

        session_store.create_session(user_id, session_id, "테스트")

        info = session_store.get_session_info(user_id, session_id)
        assert info == "abcd1234"

    def test_get_history_count(self, session_store):
        """히스토리 카운트 확인."""
        user_id = "123"
        session_id = "test-session"

        session_store.create_session(user_id, session_id, "메시지1")
        session_store.add_message(user_id, session_id, "메시지2")
        session_store.add_message(user_id, session_id, "메시지3")

        count = session_store.get_history_count(user_id, session_id)
        assert count == 3

    def test_clear_current(self, session_store):
        """현재 세션 클리어 확인."""
        user_id = "123"

        session_store.create_session(user_id, "test-session", "메시지")
        assert session_store.get_current_session_id(user_id) is not None

        session_store.clear_current(user_id)
        assert session_store.get_current_session_id(user_id) is None
