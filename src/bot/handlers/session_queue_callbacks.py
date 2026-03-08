"""Session queue conflict resolution callback handlers."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.ai import (
    get_default_model,
    get_profile_label,
    get_provider_label,
    is_supported_model,
)
from src.logging_config import logger
from ..constants import get_model_badge
from ..formatters import truncate_message
from .base import BaseHandler


class SessionQueueCallbackHandlers(BaseHandler):
    """Session queue callback handlers (sq: prefix)."""

    async def _handle_session_queue_callback(self, query, chat_id: int, callback_data: str) -> None:
        """Handle session queue callbacks (new method).

        callback_data format (with pending_key):
        - sq:wait:{pending_key}:{session_id} - Wait in this session
        - sq:switch:{pending_key}:{session_id} - Switch to another session
        - sq:new:{pending_key}:{model} - Create new session
        - sq:cancel:{pending_key} - Cancel
        """
        user_id = str(query.from_user.id)
        parts = callback_data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        pending_key = parts[2] if len(parts) > 2 else ""

        # Look up pending data by key
        pending = self._temp_pending.get(pending_key) if pending_key else None
        if not pending or pending.get("user_id") != user_id:
            await query.edit_message_text(
                "<b>Request expired</b>\n\nPlease resend the message.",
                parse_mode="HTML"
            )
            return

        message = pending["message"]
        model = pending["model"]
        is_new_session = pending["is_new_session"]
        workspace_path = pending["workspace_path"]
        current_session_id = pending["current_session_id"]
        bot = query.get_bot()

        if action == "cancel":
            self._delete_temp_pending(pending_key)
            await query.edit_message_text("Request cancelled.")
            return

        if action == "wait":
            target_session_id = current_session_id
            session_prefix = parts[3] if len(parts) > 3 else ""
            if session_prefix:
                for s in self.sessions.list_sessions(user_id):
                    if s["full_session_id"].startswith(session_prefix):
                        target_session_id = s["full_session_id"]
                        break

            repo = self._repository
            if not repo:
                await query.edit_message_text("Queue unavailable.")
                return

            if not self._is_session_locked(target_session_id):
                self._delete_temp_pending(pending_key)
                try:
                    _, start_error = self._start_detached_job(
                        chat_id=chat_id,
                        session_id=target_session_id,
                        message=message,
                        model=model,
                        workspace_path=workspace_path,
                    )
                except Exception:
                    await query.edit_message_text("❌ Failed to start detached worker.")
                    return

                if not start_error:
                    await query.edit_message_text(
                        f"<b>Processing immediately</b>\n\n"
                        f"<code>{truncate_message(message, 40)}</code>",
                        parse_mode="HTML"
                    )
                    return

                logger.warning(f"Session locked during wait callback fallback: session={target_session_id[:8]}")

            repo.save_queued_message(
                session_id=target_session_id,
                user_id=user_id,
                chat_id=chat_id,
                message=message,
                model=model,
                is_new_session=is_new_session,
                workspace_path=workspace_path or "",
            )
            position = len(repo.get_queued_messages_by_session(target_session_id))

            session_info = self.sessions.get_session_info(target_session_id)
            model_badge = get_model_badge(model)

            self._delete_temp_pending(pending_key)
            await query.edit_message_text(
                f"<b>Added to queue</b>\n\n"
                f"<code>{truncate_message(message, 40)}</code>\n\n"
                f"Session: {model_badge} <b>{session_info}</b>\n"
                f"Position: #{position}\n"
                f"Will be processed automatically after current task completes.",
                parse_mode="HTML"
            )
            return

        if action == "switch":
            target_prefix = parts[3] if len(parts) > 3 else ""
            target_session = None
            for s in self.sessions.list_sessions(user_id):
                if s["full_session_id"].startswith(target_prefix):
                    target_session = s
                    break

            if not target_session:
                await query.edit_message_text("❌ Session not found.")
                return

            target_session_id = target_session["full_session_id"]
            target_model = target_session.get("model", "sonnet")

            if self._is_session_locked(target_session_id):
                self._delete_temp_pending(pending_key)
                await self._show_session_selection_ui(
                    update=None,
                    user_id=user_id,
                    message=message,
                    current_session_id=target_session_id,
                    model=target_model,
                    is_new_session=False,
                    workspace_path=target_session.get("workspace_path") or "",
                    bot=bot,
                    chat_id=chat_id,
                )
                await query.edit_message_text("Selected session became busy. Check the new prompt below.")
                return

            self.sessions.switch_session(user_id, target_session_id)

            self._delete_temp_pending(pending_key)
            try:
                _, start_error = self._start_detached_job(
                    chat_id=chat_id,
                    session_id=target_session_id,
                    message=message,
                    model=target_model,
                    workspace_path=target_session.get("workspace_path"),
                )
            except Exception:
                await query.edit_message_text("❌ Failed to start detached worker.")
                return

            if start_error == "session_locked":
                await query.edit_message_text("❌ Selected session became busy. Please retry.")
                return

            await query.edit_message_text(
                f"<b>Session switched</b>\n\n"
                f"<code>{truncate_message(message, 40)}</code>\n\n"
                f"Starting detached processing...",
                parse_mode="HTML"
            )
            return

        if action == "new":
            provider = self.sessions.get_session_ai_provider(current_session_id) or self._get_selected_ai_provider(user_id)
            new_model = parts[3] if len(parts) > 3 else get_default_model(provider)
            if not is_supported_model(provider, new_model):
                new_model = get_default_model(provider)

            self._delete_temp_pending(pending_key)
            await query.edit_message_text(
                f"<b>Creating new {get_profile_label(provider, new_model)} session...</b>\n\n"
                f"<code>{truncate_message(message, 40)}</code>",
                parse_mode="HTML"
            )

            new_session_id = self.sessions.create_session(
                user_id=user_id,
                ai_provider=provider,
                model=new_model,
                first_message="(new session)",
            )

            try:
                _, start_error = self._start_detached_job(
                    chat_id=chat_id,
                    session_id=new_session_id,
                    message=message,
                    model=new_model,
                    workspace_path=None,
                )
            except Exception:
                await query.message.reply_text("❌ Failed to start detached worker.")
                return

            if start_error == "session_locked":
                await query.message.reply_text("❌ New session became busy unexpectedly. Please resend the message.")

            return

        await query.edit_message_text("Unknown command.")
