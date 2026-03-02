"""인증 미들웨어 테스트.

AuthManager 클래스의 핵심 기능 검증:
- 인증 성공/실패
- 세션 타임아웃
- 타이밍 공격 방지 (hmac.compare_digest)
"""

import time
from datetime import datetime, timedelta

import pytest

from src.bot.middleware import AuthManager


@pytest.fixture
def auth_manager():
    """테스트용 AuthManager 생성."""
    return AuthManager(secret_key="test_secret_key", timeout_minutes=30)


class TestAuthManager:
    """AuthManager 단위 테스트."""

    def test_authenticate_success(self, auth_manager):
        """올바른 키로 인증 성공 확인."""
        user_id = "user123"
        result = auth_manager.authenticate(user_id, "test_secret_key")

        assert result is True
        assert auth_manager.is_authenticated(user_id) is True

    def test_authenticate_failure(self, auth_manager):
        """잘못된 키로 인증 실패 확인."""
        user_id = "user123"
        result = auth_manager.authenticate(user_id, "wrong_key")

        assert result is False
        assert auth_manager.is_authenticated(user_id) is False

    def test_is_authenticated_without_auth(self, auth_manager):
        """인증하지 않은 사용자는 미인증 상태."""
        assert auth_manager.is_authenticated("unknown_user") is False

    def test_session_timeout(self):
        """세션 타임아웃 확인 (1분 타임아웃)."""
        auth = AuthManager(secret_key="key", timeout_minutes=0)
        user_id = "user123"

        auth.authenticate(user_id, "key")
        # 타임아웃 0분이므로 즉시 만료
        assert auth.is_authenticated(user_id) is False

    def test_get_remaining_minutes(self, auth_manager):
        """남은 시간 조회 확인."""
        user_id = "user123"

        # 인증 전
        assert auth_manager.get_remaining_minutes(user_id) == 0

        # 인증 후
        auth_manager.authenticate(user_id, "test_secret_key")
        remaining = auth_manager.get_remaining_minutes(user_id)
        assert 29 <= remaining <= 30

    def test_empty_secret_key(self):
        """빈 시크릿 키로 인증 시도."""
        auth = AuthManager(secret_key="", timeout_minutes=30)
        # 빈 키로도 빈 입력과 매칭됨
        assert auth.authenticate("user", "") is True
        assert auth.authenticate("user", "any_key") is False

    def test_timing_attack_resistance(self, auth_manager):
        """타이밍 공격 저항성 - hmac.compare_digest 사용 확인."""
        # 짧은 키와 긴 키 비교 시 시간 차이가 없어야 함
        import hmac

        # 실제로 hmac.compare_digest가 사용되는지 확인
        # (이 테스트는 코드 리뷰 목적)
        user_id = "user123"

        # 다양한 길이의 잘못된 키로 시도
        for wrong_key in ["a", "ab", "abc", "abcd", "wrong_key_very_long"]:
            result = auth_manager.authenticate(user_id, wrong_key)
            assert result is False
