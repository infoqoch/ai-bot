"""Telegram bot command handlers."""

import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from .formatters import format_session_quick_list, truncate_message

if TYPE_CHECKING:
    from src.claude.client import ClaudeClient
    from src.claude.session import SessionStore
    from .middleware import AuthManager

logger = logging.getLogger(__name__)


class BotHandlers:
    """Container for all bot command handlers."""

    # 유저별 Lock: 동시 메시지 처리 시 세션 데이터 유실 방지
    _user_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    # 메시지 최대 길이 (DoS 방지)
    MAX_MESSAGE_LENGTH = 4096

    def __init__(
        self,
        session_store: "SessionStore",
        claude_client: "ClaudeClient",
        auth_manager: "AuthManager",
        require_auth: bool,
        allowed_chat_ids: list[int],
    ):
        self.sessions = session_store
        self.claude = claude_client
        self.auth = auth_manager
        self.require_auth = require_auth
        self.allowed_chat_ids = allowed_chat_ids
    
    def _is_authorized(self, chat_id: int) -> bool:
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids
    
    def _is_authenticated(self, user_id: str) -> bool:
        if not self.require_auth:
            return True
        return self.auth.is_authenticated(user_id)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return
        
        user_id = str(update.effective_chat.id)
        session_info = self.sessions.get_current_session_info(user_id)
        history_count = self.sessions.get_history_count(user_id)
        
        if self.require_auth:
            is_auth = self.auth.is_authenticated(user_id)
            remaining = self.auth.get_remaining_minutes(user_id)
            auth_status = f"✅ 인증됨 ({remaining}분 남음)" if is_auth else "🔒 인증 필요"
            auth_line = f"인증: {auth_status}\n"
        else:
            auth_line = "🔓 <b>인증 없이 사용 가능</b>\n"
        
        await update.message.reply_text(
            f"🤖 <b>Claude Code Bot</b>\n\n"
            f"{auth_line}"
            f"세션: [{session_info}] ({history_count}개 질문)\n\n"
            f"/help 로 명령어 확인",
            parse_mode="HTML"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if self.require_auth:
            auth_section = (
                "🔐 인증\n"
                "/auth &lt;키&gt; - 인증 (30분 유효)\n"
                "/status - 인증 상태 확인\n\n"
            )
        else:
            auth_section = "🔓 <b>인증 없이 바로 사용 가능</b>\n\n"
        
        await update.message.reply_text(
            "📖 <b>명령어 목록</b>\n\n"
            f"{auth_section}"
            "💬 세션\n"
            "/new - 새 Claude 세션 시작\n"
            "/session - 현재 세션 정보 + 대화 내용\n"
            "/session_list - 세션 목록 + AI 요약\n\n"
            "ℹ️ 기타\n"
            "/help - 이 도움말",
            parse_mode="HTML"
        )
    
    async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /auth command."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return
        
        user_id = str(update.effective_chat.id)
        
        if not context.args:
            await update.message.reply_text("사용법: /auth <비밀키>")
            return
        
        key = context.args[0]
        
        if self.auth.authenticate(user_id, key):
            await update.message.reply_text("✅ 인증 성공! 30분간 유효합니다.")
            logger.info(f"[{user_id}] 인증 성공")
        else:
            await update.message.reply_text("❌ 인증 실패. 키가 틀렸습니다.")
            logger.warning(f"[{user_id}] 인증 실패")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return
        
        user_id = str(update.effective_chat.id)
        
        if self.auth.is_authenticated(user_id):
            remaining = self.auth.get_remaining_minutes(user_id)
            await update.message.reply_text(f"✅ 인증됨 ({remaining}분 남음)")
        else:
            await update.message.reply_text("🔒 인증 필요\n/auth <키>로 인증하세요.")
    
    async def new_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new command."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return
        
        user_id = str(update.effective_chat.id)
        
        if not self._is_authenticated(user_id):
            await update.message.reply_text("🔒 먼저 인증이 필요합니다.\n/auth <키>")
            return
        
        self.sessions.clear_current(user_id)
        await update.message.reply_text("🔄 새 Claude 세션을 시작합니다.")
    
    async def session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /session command - show current session info."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return
        
        user_id = str(update.effective_chat.id)
        
        if not self._is_authenticated(user_id):
            await update.message.reply_text("🔒 먼저 인증이 필요합니다.\n/auth <키>")
            return
        
        summary = self.sessions.get_session_summary(user_id)
        
        if not summary:
            await update.message.reply_text(
                "📭 활성 세션이 없습니다.\n\n"
                "• 메시지를 보내면 새 세션 시작\n"
                "• /session_list - 저장된 세션 목록",
                parse_mode="HTML"
            )
            return
        
        session_id = summary["session_id"][:8]
        created = summary["created_at"][:19]
        last_used = summary["last_used"][:19]
        history = summary["history"]
        count = len(history)
        
        # Recent 10 messages
        recent = history[-10:]
        history_lines = []
        start_idx = len(history) - len(recent) + 1
        for i, q in enumerate(recent, start=start_idx):
            short_q = truncate_message(q, 40)
            history_lines.append(f"{i}. {short_q}")
        
        history_text = "\n".join(history_lines) if history_lines else "(없음)"
        
        await update.message.reply_text(
            f"📊 <b>현재 세션</b>\n\n"
            f"• ID: <code>{session_id}</code>\n"
            f"• 시작: {created}\n"
            f"• 최근: {last_used}\n"
            f"• 질문: {count}개\n\n"
            f"<b>대화 내용</b> (최근 10개)\n{history_text}",
            parse_mode="HTML"
        )
    
    async def session_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /session_list command."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return
        
        user_id = str(update.effective_chat.id)
        
        if not self._is_authenticated(user_id):
            await update.message.reply_text("🔒 먼저 인증이 필요합니다.\n/auth <키>")
            return
        
        sessions = self.sessions.list_sessions(user_id)
        if not sessions:
            await update.message.reply_text("📭 저장된 세션이 없습니다.")
            return
        
        # Get histories for quick list
        histories = {
            s["full_session_id"]: self.sessions.get_session_history(user_id, s["full_session_id"])
            for s in sessions
        }
        
        # Send quick list first
        quick_list = format_session_quick_list(sessions, histories)
        await update.message.reply_text(
            quick_list + "\n\n🔍 AI 분석 중...",
            parse_mode="HTML"
        )
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        # Generate AI summaries
        analysis_lines = []
        for s in sessions:
            history = histories.get(s["full_session_id"], [])
            if history:
                summary = await self.claude.summarize(history)
            else:
                summary = "(내용 없음)"
            
            analysis_lines.append(f"<b>/s_{s['session_id']}</b>\n{summary}")
        
        await update.message.reply_text(
            "📊 <b>AI 분석 결과</b>\n\n" + "\n\n".join(analysis_lines),
            parse_mode="HTML"
        )
    
    async def switch_session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /s_<id> command for session switching."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return
        
        user_id = str(update.effective_chat.id)
        
        if not self._is_authenticated(user_id):
            await update.message.reply_text("🔒 먼저 인증이 필요합니다.\n/auth <키>")
            return
        
        text = update.message.text
        if not text.startswith("/s_"):
            return
        
        target = text[3:]  # Extract session prefix
        
        target_info = self.sessions.get_session_by_prefix(user_id, target)
        if not target_info:
            await update.message.reply_text(f"❌ 세션 '{target}'을 찾을 수 없습니다.")
            return
        
        if self.sessions.switch_session(user_id, target):
            await update.message.reply_text(
                f"✅ 세션 전환 완료!\n\n"
                f"• ID: <code>{target_info['session_id']}</code>\n"
                f"• 질문: {target_info['history_count']}개",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ 세션 전환 실패")
    
    def _format_session_list_with_lock(self, user_id: str) -> str:
        """세션 목록을 Lock 상태와 함께 포맷."""
        sessions = self.sessions.list_sessions(user_id)
        if not sessions:
            return "📭 세션 없음"

        current_session_id = self.sessions.get_current_session_id(user_id)
        is_locked = self._user_locks[user_id].locked()

        lines = ["📋 <b>세션 목록:</b>"]
        for s in sessions[:5]:  # 최대 5개
            sid = s["session_id"]
            is_current = s["full_session_id"] == current_session_id

            if is_current and is_locked:
                status = "🔒 처리 중"
            elif is_current:
                status = "◀ 현재"
            else:
                status = "✅"

            lines.append(f"• <code>{sid}</code> {status}")

        return "\n".join(lines)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages."""
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("⛔ 권한이 없습니다.")
            return

        user_id = str(update.effective_chat.id)
        message = update.message.text

        # 메시지 길이 제한 (DoS 방지)
        if len(message) > self.MAX_MESSAGE_LENGTH:
            original_len = len(message)
            message = message[:self.MAX_MESSAGE_LENGTH]
            logger.warning(f"[{user_id}] 메시지 길이 제한 적용: {original_len} -> {self.MAX_MESSAGE_LENGTH}")

        if not self._is_authenticated(user_id):
            await update.message.reply_text(
                "🔒 인증이 필요합니다.\n"
                "/auth <키>로 인증하세요. (30분간 유효)"
            )
            return

        # Lock 상태 확인 (블로킹 전)
        if self._user_locks[user_id].locked():
            session_list = self._format_session_list_with_lock(user_id)
            await update.message.reply_text(
                f"⏳ 이전 메시지 처리 중입니다.\n\n"
                f"{session_list}\n\n"
                f"/new - 새 세션에서 시작",
                parse_mode="HTML"
            )
            return

        # 유저별 Lock으로 동시 요청 순차 처리
        async with self._user_locks[user_id]:
            logger.info(f"[{user_id}] 메시지: {message[:50]}...")

            # Show typing indicator
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action="typing"
            )

            # Check for existing session
            session_id = self.sessions.get_current_session_id(user_id)

            if session_id:
                chat_session_id = session_id
                resume = True
            else:
                chat_session_id = self.sessions.create_session(user_id, message)
                resume = False

            # Claude 호출을 Task로 실행
            chat_task = asyncio.create_task(
                self.claude.chat(message, chat_session_id, resume=resume)
            )

            # 60초 대기, 초과 시 알림
            notification_sent = False
            try:
                response, error = await asyncio.wait_for(chat_task, timeout=60)
            except asyncio.TimeoutError:
                # 60초 초과 - 알림 전송 후 계속 대기
                session_list = self._format_session_list_with_lock(user_id)
                await update.message.reply_text(
                    f"⏳ 1분 초과. 계속 대기 중입니다.\n"
                    f"다른 세션에서 작업하시겠습니까?\n\n"
                    f"{session_list}\n\n"
                    f"/new - 새 세션 시작",
                    parse_mode="HTML"
                )
                notification_sent = True
                # 계속 대기 (타임아웃 없이)
                response, error = await chat_task

            # 세션 처리
            if error == "SESSION_NOT_FOUND":
                # 세션 만료, 새로 생성
                self.sessions.clear_current(user_id)
                new_session_id = self.sessions.create_session(user_id, message)
                response, error = await self.claude.chat(message, new_session_id, resume=False)
            elif resume:
                self.sessions.add_message(user_id, message)

            if error == "TIMEOUT":
                response = "⏱️ 응답 시간 초과. 다시 시도해주세요."
            elif error and error != "SESSION_NOT_FOUND":
                response = f"❌ 오류 발생: {error}"

            # Add session info prefix
            session_info = self.sessions.get_current_session_info(user_id)
            history_count = self.sessions.get_history_count(user_id)
            prefix = f"<b>[{session_info}|#{history_count}]</b>\n\n"

            full_response = prefix + response

            # Handle message length limit (4096 chars)
            await self._send_long_message(update, full_response)
    
    async def _send_long_message(self, update: Update, text: str, max_length: int = 4000) -> None:
        """Send message, splitting if too long."""
        if len(text) <= max_length:
            try:
                await update.message.reply_text(text, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(text)
            return
        
        # Split into chunks
        chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)]
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(chunk)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        # 내부 로그에는 상세 오류 기록
        logger.error(f"Error: {context.error}", exc_info=context.error)

        if update and update.effective_chat:
            # 사용자에게는 일반적인 오류 메시지만 표시 (보안)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
