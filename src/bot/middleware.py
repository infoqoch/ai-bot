"""Authentication and authorization middleware."""

import hmac
from datetime import datetime, timedelta
from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

from telegram import Update
from telegram.ext import ContextTypes

from src.logging_config import logger

if TYPE_CHECKING:
    from src.repository import Repository

F = TypeVar('F', bound=Callable)


class AuthManager:
    """Manages user authentication sessions."""

    def __init__(self, secret_key: str, timeout_minutes: int = 30, repository: "Repository" = None):
        logger.trace(f"AuthManager.__init__() - timeout={timeout_minutes}min")
        self.secret_key = secret_key
        self.timeout_minutes = timeout_minutes
        self._sessions: dict[str, datetime] = {}
        self._repository = repository

    def is_authenticated(self, user_id: str) -> bool:
        logger.trace(f"is_authenticated() - user_id={user_id}")

        if user_id in self._sessions:
            last_auth = self._sessions[user_id]
            elapsed = datetime.now() - last_auth
            is_valid = elapsed < timedelta(minutes=self.timeout_minutes)
            logger.trace(f"memory session check - last_auth={last_auth}, elapsed={elapsed}, valid={is_valid}")
            if not is_valid:
                logger.debug(f"auth session expired - user_id={user_id}")
                del self._sessions[user_id]
                if self._repository:
                    self._repository.delete_auth_session(user_id)
            return is_valid

        # 메모리에 없으면 DB 확인
        if self._repository:
            authenticated_at = self._repository.get_auth_session(user_id)
            if authenticated_at:
                elapsed = datetime.now() - authenticated_at
                is_valid = elapsed < timedelta(minutes=self.timeout_minutes)
                if is_valid:
                    self._sessions[user_id] = authenticated_at
                    logger.debug(f"auth session restored from DB - user_id={user_id}")
                    return True
                else:
                    self._repository.delete_auth_session(user_id)

        logger.trace("no auth session")
        return False

    def authenticate(self, user_id: str, key: str) -> bool:
        logger.trace(f"authenticate() - user_id={user_id}, key_len={len(key)}")

        # 타이밍 공격 방지를 위해 상수 시간 비교 사용
        if hmac.compare_digest(key, self.secret_key):
            now = datetime.now()
            self._sessions[user_id] = now
            if self._repository:
                self._repository.save_auth_session(user_id, now)
            logger.info(f"auth success - user_id={user_id}")
            logger.trace(f"auth session created - expires_at={now + timedelta(minutes=self.timeout_minutes)}")
            return True

        logger.warning(f"auth failed - user_id={user_id}, invalid key")
        return False

    def get_remaining_minutes(self, user_id: str) -> int:
        logger.trace(f"get_remaining_minutes() - user_id={user_id}")

        if user_id not in self._sessions:
            logger.trace("no session - returning 0 min")
            return 0

        elapsed = datetime.now() - self._sessions[user_id]
        remaining = self.timeout_minutes - int(elapsed.total_seconds() / 60)
        result = max(0, remaining)

        logger.trace(f"remaining time: {result}min")
        return result

    def cleanup_expired(self) -> int:
        """만료된 인증 세션 정리. 정리된 수 반환."""
        logger.trace("cleanup_expired() 시작")

        now = datetime.now()
        expired = [
            uid for uid, last_auth in self._sessions.items()
            if now - last_auth >= timedelta(minutes=self.timeout_minutes)
        ]

        logger.trace(f"expired sessions: {len(expired)}")

        for uid in expired:
            del self._sessions[uid]
            logger.trace(f"session deleted: user_id={uid}")

        if self._repository:
            self._repository.clear_expired_auth_sessions(self.timeout_minutes)

        return len(expired)

    def restore_from_db(self) -> int:
        """봇 시작 시 DB에서 만료되지 않은 세션을 메모리로 로드. 복원된 수 반환."""
        if not self._repository:
            return 0

        self._repository.clear_expired_auth_sessions(self.timeout_minutes)
        all_sessions = self._repository.get_all_auth_sessions()
        count = 0
        now = datetime.now()
        for user_id, authenticated_at in all_sessions.items():
            if now - authenticated_at < timedelta(minutes=self.timeout_minutes):
                self._sessions[user_id] = authenticated_at
                count += 1
                logger.debug(f"auth session restored - user_id={user_id}")

        logger.info(f"restored {count} auth sessions from DB")
        return count


def require_auth(
    auth_manager: AuthManager,
    require_auth_setting: bool,
    allowed_chat_ids: list[int],
):
    """Decorator factory for auth-protected handlers."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            chat_id = update.effective_chat.id
            user_id = str(chat_id)

            logger.trace(f"require_auth decorator - chat_id={chat_id}")

            # Check allowed chat IDs
            if allowed_chat_ids and chat_id not in allowed_chat_ids:
                logger.debug(f"unauthorized - chat_id={chat_id}")
                await update.message.reply_text("⛔ Access denied.")
                return

            # Check authentication if required
            if require_auth_setting and not auth_manager.is_authenticated(user_id):
                logger.debug(f"auth required - user_id={user_id}")
                await update.message.reply_text(
                    "🔒 Authentication required.\n"
                    f"Use /auth <key> to authenticate. (Valid for {auth_manager.timeout_minutes}m)\n"
                    "/help for commands"
                )
                return

            logger.trace("auth passed - executing handler")
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


def require_allowed_chat(allowed_chat_ids: list[int]):
    """Decorator factory for chat ID restriction."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            chat_id = update.effective_chat.id

            logger.trace(f"require_allowed_chat decorator - chat_id={chat_id}")

            if allowed_chat_ids and chat_id not in allowed_chat_ids:
                logger.debug(f"unauthorized - chat_id={chat_id}")
                await update.message.reply_text("⛔ Access denied.")
                return

            logger.trace("auth passed - executing handler")
            return await func(update, context, *args, **kwargs)

        return wrapper
    return decorator


def authorized_only(method: F) -> F:
    """권한 검사 데코레이터 (BotHandlers 메서드용)."""
    @wraps(method)
    async def wrapper(self, update, context, *args, **kwargs):
        chat_id = update.effective_chat.id
        logger.trace(f"authorized_only decorator - chat_id={chat_id}")

        if not self._is_authorized(chat_id):
            logger.debug(f"unauthorized - chat_id={chat_id}")
            await update.message.reply_text("⛔ Access denied.")
            return

        logger.trace("auth passed")
        return await method(self, update, context, *args, **kwargs)
    return wrapper


def authenticated_only(method: F) -> F:
    """인증 검사 데코레이터 (BotHandlers 메서드용).

    Note: authorized_only와 함께 사용 시 authorized_only를 먼저 적용해야 함.
    """
    @wraps(method)
    async def wrapper(self, update, context, *args, **kwargs):
        user_id = str(update.effective_chat.id)
        logger.trace(f"authenticated_only decorator - user_id={user_id}")

        if not self._is_authenticated(user_id):
            logger.debug(f"auth required - user_id={user_id}")
            await update.message.reply_text(
                "🔒 Authentication required first.\n/auth <key>"
            )
            return

        logger.trace("auth passed")
        return await method(self, update, context, *args, **kwargs)
    return wrapper
