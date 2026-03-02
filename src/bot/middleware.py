"""Authentication and authorization middleware."""

from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes


class AuthManager:
    """Manages user authentication sessions."""
    
    def __init__(self, secret_key: str, timeout_minutes: int = 30):
        self.secret_key = secret_key
        self.timeout_minutes = timeout_minutes
        self._sessions: dict[str, datetime] = {}
    
    def is_authenticated(self, user_id: str) -> bool:
        if user_id not in self._sessions:
            return False
        
        last_auth = self._sessions[user_id]
        return datetime.now() - last_auth < timedelta(minutes=self.timeout_minutes)
    
    def authenticate(self, user_id: str, key: str) -> bool:
        if key == self.secret_key:
            self._sessions[user_id] = datetime.now()
            return True
        return False
    
    def get_remaining_minutes(self, user_id: str) -> int:
        if user_id not in self._sessions:
            return 0
        
        elapsed = datetime.now() - self._sessions[user_id]
        remaining = self.timeout_minutes - int(elapsed.total_seconds() / 60)
        return max(0, remaining)


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
            
            # Check allowed chat IDs
            if allowed_chat_ids and chat_id not in allowed_chat_ids:
                await update.message.reply_text("⛔ 권한이 없습니다.")
                return
            
            # Check authentication if required
            if require_auth_setting and not auth_manager.is_authenticated(user_id):
                await update.message.reply_text(
                    "🔒 인증이 필요합니다.\n/auth <키>로 인증하세요. (30분간 유효)"
                )
                return
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


def require_allowed_chat(allowed_chat_ids: list[int]):
    """Decorator factory for chat ID restriction."""
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            chat_id = update.effective_chat.id
            
            if allowed_chat_ids and chat_id not in allowed_chat_ids:
                await update.message.reply_text("⛔ 권한이 없습니다.")
                return
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator
