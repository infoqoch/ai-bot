"""Telegram 핸들러 테스트.

BotHandlers 클래스의 핵심 기능 검증:
- 권한 검사
- 인증 검사
- 메시지 길이 제한
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers import BotHandlers


@pytest.fixture
def mock_session_store():
    """모의 세션 저장소."""
    store = MagicMock()
    store.get_current_session_info.return_value = "abc12345"
    store.get_history_count.return_value = 5
    store.get_current_session_id.return_value = None
    store.create_session.return_value = "new-session-id"
    return store


@pytest.fixture
def mock_claude_client():
    """모의 Claude 클라이언트."""
    client = MagicMock()
    client.chat = AsyncMock(return_value=("응답 텍스트", None))
    return client


@pytest.fixture
def mock_auth_manager():
    """모의 인증 관리자."""
    auth = MagicMock()
    auth.is_authenticated.return_value = True
    auth.get_remaining_minutes.return_value = 25
    return auth


@pytest.fixture
def handlers(mock_session_store, mock_claude_client, mock_auth_manager):
    """테스트용 핸들러 생성."""
    return BotHandlers(
        session_store=mock_session_store,
        claude_client=mock_claude_client,
        auth_manager=mock_auth_manager,
        require_auth=True,
        allowed_chat_ids=[12345],
    )


class TestBotHandlers:
    """BotHandlers 단위 테스트."""

    def test_is_authorized_allowed(self, handlers):
        """허용된 채팅 ID 확인."""
        assert handlers._is_authorized(12345) is True

    def test_is_authorized_not_allowed(self, handlers):
        """허용되지 않은 채팅 ID 확인."""
        assert handlers._is_authorized(99999) is False

    def test_is_authorized_empty_list(self, mock_session_store, mock_claude_client, mock_auth_manager):
        """빈 허용 목록은 모두 허용."""
        handlers = BotHandlers(
            session_store=mock_session_store,
            claude_client=mock_claude_client,
            auth_manager=mock_auth_manager,
            require_auth=True,
            allowed_chat_ids=[],
        )
        assert handlers._is_authorized(99999) is True

    def test_is_authenticated_required(self, handlers, mock_auth_manager):
        """인증 필수 시 인증 확인."""
        mock_auth_manager.is_authenticated.return_value = True
        assert handlers._is_authenticated("user123") is True

        mock_auth_manager.is_authenticated.return_value = False
        assert handlers._is_authenticated("user123") is False

    def test_is_authenticated_not_required(self, mock_session_store, mock_claude_client, mock_auth_manager):
        """인증 불필요 시 항상 True."""
        handlers = BotHandlers(
            session_store=mock_session_store,
            claude_client=mock_claude_client,
            auth_manager=mock_auth_manager,
            require_auth=False,
            allowed_chat_ids=[],
        )
        mock_auth_manager.is_authenticated.return_value = False
        assert handlers._is_authenticated("user123") is True

    def test_max_message_length_constant(self, handlers):
        """메시지 최대 길이 상수 확인."""
        assert handlers.MAX_MESSAGE_LENGTH == 4096

    @pytest.mark.asyncio
    async def test_start_unauthorized(self, handlers):
        """권한 없는 사용자의 /start 처리."""
        update = MagicMock()
        update.effective_chat.id = 99999  # 허용되지 않은 ID
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await handlers.start(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "권한이 없습니다" in call_args

    @pytest.mark.asyncio
    async def test_handle_message_unauthenticated(self, handlers, mock_auth_manager):
        """미인증 사용자의 메시지 처리."""
        mock_auth_manager.is_authenticated.return_value = False

        update = MagicMock()
        update.effective_chat.id = 12345
        update.message.text = "Hello"
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await handlers.handle_message(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args[0][0]
        assert "인증이 필요합니다" in call_args

    @pytest.mark.asyncio
    async def test_error_handler_generic_message(self, handlers):
        """에러 핸들러의 일반 메시지 응답 확인."""
        update = MagicMock()
        update.effective_chat.id = 12345
        context = MagicMock()
        context.error = Exception("Internal error details")
        context.bot.send_message = AsyncMock()

        await handlers.error_handler(update, context)

        # 사용자에게는 일반적인 메시지만 전송되어야 함
        call_kwargs = context.bot.send_message.call_args[1]
        assert "Internal error details" not in call_kwargs["text"]
        assert "오류가 발생했습니다" in call_kwargs["text"]
