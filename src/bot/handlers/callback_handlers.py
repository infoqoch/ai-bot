"""Callback query handlers - router and small utility callbacks."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.ai import (
    get_default_model,
    get_profile_label,
    get_provider_label,
    get_provider_profiles,
    is_supported_model,
)
from src.logging_config import logger, clear_context
from ..constants import get_model_emoji
from ..formatters import escape_html
from .base import BaseHandler


class CallbackHandlers(BaseHandler):
    """Callback query handlers - router and small utility callbacks."""

    async def callback_query_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callbacks."""
        query = update.callback_query
        if not query:
            return

        chat_id = query.message.chat_id if query.message else None
        if not chat_id:
            return

        self._setup_request_context(chat_id)
        callback_data = query.data
        logger.info(f"Callback query: {callback_data} (chat_id={chat_id})")

        if not self._is_authorized(chat_id):
            logger.debug("Callback denied - unauthorized")
            await query.answer("⛔ Access denied.", show_alert=True)
            clear_context()
            return

        if not self._is_authenticated(str(chat_id)):
            logger.debug("Callback denied - auth required")
            await query.answer("🔒 Authentication required.\n/auth <key>", show_alert=True)
            clear_context()
            return

        await query.answer()

        # Plugin auto-routing (CALLBACK_PREFIX 기반)
        if self.plugins:
            plugin = self.plugins.get_plugin_for_callback(callback_data)
            if plugin:
                await self._handle_plugin_callback(query, chat_id, callback_data, plugin)
                return

        if callback_data.startswith("ai:"):
            await self._handle_ai_callback(query, chat_id, callback_data)
            return

        # Session callback
        if callback_data.startswith("sess:"):
            await self._handle_session_callback(query, chat_id, callback_data)
            return

        # Tasks callback
        if callback_data.startswith("tasks:"):
            await self._handle_tasks_callback(query, chat_id)
            return

        # Scheduler callback
        if callback_data.startswith("sched:"):
            await self._handle_scheduler_callback(query, chat_id, callback_data)
            return

        # Workspace callback
        if callback_data.startswith("ws:"):
            await self._handle_workspace_callback(query, chat_id, callback_data)
            return

        # Session queue callback (new method)
        if callback_data.startswith("sq:"):
            await self._handle_session_queue_callback(query, chat_id, callback_data)
            return

        logger.warning(f"Unknown callback: {callback_data}")

    async def _handle_todo_force_reply(self, update: Update, chat_id: int, message: str) -> None:
        """Handle Todo ForceReply response."""
        logger.info(f"Todo ForceReply processing: msg={message[:50]}")

        todo_plugin = None
        if self.plugins:
            todo_plugin = self.plugins.get_plugin_by_name("todo")

        if not todo_plugin or not hasattr(todo_plugin, 'handle_force_reply'):
            await update.message.reply_text("Todo plugin not found.")
            return

        result = todo_plugin.handle_force_reply(message, chat_id)

        await update.message.reply_text(
            text=result.get("text", ""),
            reply_markup=result.get("reply_markup"),
            parse_mode="HTML"
        )

    async def _handle_new_session_force_reply(self, update: Update, chat_id: int, name: str, model: str) -> None:
        """Handle session creation ForceReply response."""
        logger.info(f"Session creation ForceReply processing: model={model}, name={name}")

        user_id = str(chat_id)
        provider = self._get_selected_ai_provider(user_id)
        model_name = model if is_supported_model(provider, model) else get_default_model(provider)

        session_name = name.strip()[:50] if name.strip() else ""

        session_id = self.sessions.create_session(
            user_id=user_id,
            ai_provider=provider,
            model=model_name,
            name=session_name,
            first_message="(new session)",
        )
        short_id = session_id[:8]

        model_emoji = get_model_emoji(model_name)
        name_line = f"\n<b>Name:</b> {escape_html(session_name)}" if session_name else ""

        keyboard = [[
            InlineKeyboardButton("Session List", callback_data="sess:list"),
        ]]

        await update.message.reply_text(
            text=f"New session created!\n\n"
                 f"<b>AI:</b> {get_provider_label(provider)}\n"
                 f"{model_emoji} <b>Model:</b> {get_profile_label(provider, model_name)}\n"
                 f"<b>ID:</b> <code>{short_id}</code>{name_line}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    async def _handle_rename_force_reply(self, update: Update, chat_id: int, new_name: str, session_id: str) -> None:
        """Handle session rename ForceReply response."""
        logger.info(f"Rename ForceReply processing: session={session_id[:8]}, name={new_name}")

        new_name = new_name.strip()
        if not new_name:
            await update.message.reply_text("❌ Name cannot be empty.")
            return

        if len(new_name) > 50:
            await update.message.reply_text("❌ Name too long. (max 50 chars)")
            return

        if self.sessions.rename_session(session_id, new_name):
            logger.info(f"Session renamed: {session_id[:8]} -> {new_name}")
            await update.message.reply_text(
                f"✅ Session renamed!\n\n"
                f"- Session: <code>{session_id[:8]}</code>\n"
                f"- Name: {escape_html(new_name)}",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("❌ Rename failed.")

    async def _handle_memo_force_reply(self, update: Update, chat_id: int, message: str) -> None:
        """Handle memo add ForceReply response."""
        logger.info(f"Memo ForceReply processing: msg={message[:50]}")

        memo_plugin = None
        if self.plugins:
            memo_plugin = self.plugins.get_plugin_by_name("memo")

        if not memo_plugin or not hasattr(memo_plugin, 'handle_force_reply'):
            await update.message.reply_text("Memo plugin not found.")
            return

        result = memo_plugin.handle_force_reply(message, chat_id)

        await update.message.reply_text(
            text=result.get("text", ""),
            reply_markup=result.get("reply_markup"),
            parse_mode="HTML"
        )

    async def _handle_plugin_callback(self, query, chat_id: int, callback_data: str, plugin) -> None:
        """Handle plugin callback with auto-routing."""
        try:
            result = await plugin.handle_callback_async(callback_data, chat_id)

            # ForceReply 처리
            if result.get("force_reply"):
                await query.edit_message_text(
                    text=result.get("text", "Enter input"),
                    parse_mode="HTML"
                )
                marker_text = result.get("force_reply_marker", plugin.FORCE_REPLY_MARKER or f"{plugin.name}_add")
                await query.message.reply_text(
                    text=marker_text,
                    reply_markup=result["force_reply"],
                    parse_mode="HTML"
                )
                return

            # 메시지 편집/전송
            if result.get("edit", True) and query.message:
                await query.edit_message_text(
                    text=result.get("text", ""),
                    reply_markup=result.get("reply_markup"),
                    parse_mode="HTML"
                )
            else:
                await query.message.reply_text(
                    text=result.get("text", ""),
                    reply_markup=result.get("reply_markup"),
                    parse_mode="HTML"
                )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                logger.warning(f"{plugin.name} callback BadRequest: {e}")
        except Exception as e:
            logger.exception(f"{plugin.name} callback error: {e}")
            try:
                await query.edit_message_text(
                    text=f"Error occurred.\n\n<code>{escape_html(str(e))}</code>",
                    parse_mode="HTML"
                )
            except:
                pass

    async def _handle_ai_callback(self, query, chat_id: int, callback_data: str) -> None:
        """Handle provider selection callbacks."""
        user_id = str(chat_id)
        parts = callback_data.split(":")
        action = parts[1] if len(parts) > 1 else ""

        if action == "cancel":
            await query.edit_message_text("Provider selection cancelled.")
            return

        if action == "open":
            provider = self._get_selected_ai_provider(user_id)
            keyboard = self._build_ai_selector_keyboard(provider)
            keyboard.append([
                InlineKeyboardButton("📋 Session List", callback_data="sess:list"),
                InlineKeyboardButton("🆕 New Session", callback_data="sess:new"),
            ])
            await query.edit_message_text(
                f"<b>Select AI</b>\n\n"
                f"Current AI: <b>{get_provider_label(provider)}</b>\n\n"
                f"Choose which provider `/new`, `/sl`, `/session`, `/model`, `/ai`, and normal chat should use.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            return

        if action == "select" and len(parts) > 2:
            provider = parts[2]
            self._set_selected_ai_provider(user_id, provider)
            current_session_id = self.sessions.get_current_session_id(user_id, provider)
            current_line = (
                f"Current session: <code>{current_session_id[:8]}</code>"
                if current_session_id else
                "Current session: none"
            )
            keyboard = [
                [InlineKeyboardButton("📋 Session List", callback_data="sess:list")],
                [InlineKeyboardButton("🆕 New Session", callback_data="sess:new")],
            ]
            await query.edit_message_text(
                f"✅ Current AI switched to <b>{get_provider_label(provider)}</b>.\n\n"
                f"{current_line}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
            )
            return

        await query.edit_message_text("Unknown AI selection request.")

    async def _handle_tasks_callback(self, query, chat_id: int) -> None:
        """Handle task status callback - same as /tasks."""
        user_id = str(chat_id)
        text, keyboard = self._build_tasks_status(user_id)

        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
