"""Session-related callback handlers."""
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.error import BadRequest

from src.ai import (
    get_default_model,
    get_profile_label,
    get_profile_short_label,
    get_provider_label,
    get_provider_profiles,
    is_supported_model,
)
from src.logging_config import logger
from ..constants import get_model_emoji, get_model_badge
from ..formatters import escape_html, truncate_message
from .base import BaseHandler


class SessionCallbackHandlers(BaseHandler):
    """Session callback handlers (sess: prefix)."""

    async def _handle_session_callback(self, query, chat_id: int, callback_data: str) -> None:
        """Handle session callbacks."""
        try:
            parts = callback_data.split(":")
            if len(parts) < 2:
                await query.edit_message_text("Invalid request")
                return

            action = parts[1]
            user_id = str(chat_id)
            selected_provider = self._get_selected_ai_provider(user_id)

            if action == "new":
                model = parts[2] if len(parts) > 2 else get_default_model(selected_provider)
                await self._handle_new_session_name_prompt(query, chat_id, model)

            elif action == "new_confirm":
                model = parts[2] if len(parts) > 2 else get_default_model(selected_provider)
                await self._handle_new_session_callback(query, chat_id, model, "")

            elif action == "switch":
                session_id = parts[2] if len(parts) > 2 else ""
                await self._handle_switch_session_callback(query, chat_id, session_id)

            elif action == "delete":
                session_id = parts[2] if len(parts) > 2 else ""
                await self._handle_delete_session_confirm(query, chat_id, session_id)

            elif action == "confirm_del":
                session_id = parts[2] if len(parts) > 2 else ""
                await self._handle_delete_session_execute(query, chat_id, session_id)

            elif action == "history":
                session_id = parts[2] if len(parts) > 2 else ""
                await self._handle_history_callback(query, chat_id, session_id)

            elif action == "list":
                await self._handle_session_list_callback(query, chat_id)

            elif action == "rename":
                session_id = parts[2] if len(parts) > 2 else ""
                await self._handle_rename_prompt_callback(query, chat_id, session_id)

            elif action == "model":
                model = parts[2] if len(parts) > 2 else "sonnet"
                session_id = parts[3] if len(parts) > 3 else ""
                await self._handle_model_change_callback(query, chat_id, model, session_id)

            elif action == "cancel":
                await self._handle_session_list_callback(query, chat_id)

            else:
                await query.edit_message_text("Unknown command")

        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                logger.warning(f"Session callback BadRequest: {e}")
        except Exception as e:
            logger.exception(f"Session callback error: {e}")
            try:
                await query.edit_message_text(
                    text=f"Error occurred.\n\n<code>{escape_html(str(e))}</code>",
                    parse_mode="HTML"
                )
            except:
                pass

    async def _handle_new_session_name_prompt(self, query, chat_id: int, model: str) -> None:
        """Prompt for new session name."""
        provider = self._get_selected_ai_provider(str(chat_id))
        normalized_model = model if is_supported_model(provider, model) else get_default_model(provider)
        model_emoji = get_model_emoji(normalized_model)

        await query.edit_message_text(
            text=f"{model_emoji} <b>{get_profile_label(provider, normalized_model)}</b> session creation\n\n"
                 f"Current AI: <b>{get_provider_label(provider)}</b>\n\n"
                 f"Enter session name:",
            parse_mode="HTML"
        )

        await query.message.reply_text(
            text=f"Enter session name (sess_name:{normalized_model})",
            reply_markup=ForceReply(selective=True, input_field_placeholder="Session name...")
        )

    async def _handle_rename_prompt_callback(self, query, chat_id: int, session_id: str) -> None:
        """Handle rename button - prompt for new name via ForceReply."""
        session_name = self.sessions.get_session_name(session_id) or "(unnamed)"

        await query.edit_message_text(
            text=f"✏️ <b>Rename Session</b>\n\n"
            f"- Current: {escape_html(session_name)}\n"
            f"- ID: <code>{session_id[:8]}</code>\n\n"
            f"Enter new name below:",
            parse_mode="HTML"
        )

        await query.message.reply_text(
            text=f"Enter new name (sess_rename:{session_id})",
            reply_markup=ForceReply(selective=True, input_field_placeholder="New session name...")
        )

    async def _handle_new_session_callback(self, query, chat_id: int, model: str, name: str = "") -> None:
        """Handle new session creation callback."""
        user_id = str(chat_id)
        provider = self._get_selected_ai_provider(user_id)
        model_name = model if is_supported_model(provider, model) else get_default_model(provider)

        session_id = self.sessions.create_session(
            user_id=user_id,
            ai_provider=provider,
            model=model_name,
            name=name,
            first_message="(new session)",
        )
        short_id = session_id[:8]

        model_emoji = get_model_emoji(model_name)

        keyboard = [
            [
                InlineKeyboardButton("Session List", callback_data="sess:list"),
            ]
        ]

        await query.edit_message_text(
            text=f"New session created!\n\n"
                 f"<b>AI:</b> {get_provider_label(provider)}\n"
                 f"{model_emoji} <b>Model:</b> {get_profile_label(provider, model_name)}\n"
                 f"<b>ID:</b> <code>{short_id}</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    async def _handle_switch_session_callback(self, query, chat_id: int, session_id: str) -> None:
        """Handle session switch callback - shows full session info like /session."""
        user_id = str(chat_id)
        session = self.sessions.get_session_by_prefix(user_id, session_id[:8])
        if not session:
            await query.edit_message_text("❌ Session not found.")
            return

        full_session_id = session.get("full_session_id", session_id)
        self.sessions.switch_session(user_id, full_session_id)
        short_id = full_session_id[:8]
        session_name = session.get("name") or ""
        model = session.get("model", "sonnet")
        provider = session.get("ai_provider", self._get_selected_ai_provider(user_id))
        model_emoji = get_model_emoji(model)

        history_entries = self.sessions.get_session_history_entries(full_session_id)
        count = len(history_entries)

        recent = history_entries[-10:]
        history_lines = []
        start_idx = len(history_entries) - len(recent) + 1

        for i, entry in enumerate(recent, start=start_idx):
            msg = entry.get("message", "") if isinstance(entry, dict) else str(entry)
            processor = entry.get("processor", "claude") if isinstance(entry, dict) else "claude"
            emoji = "[plugin]" if processor.startswith("plugin:") else {"command": "[cmd]", "rejected": "[x]"}.get(processor, "")
            short_q = truncate_message(msg, 35)
            history_lines.append(f"{i}. {emoji} {escape_html(short_q)}")

        history_text = "\n".join(history_lines) if history_lines else "(empty)"
        name_line = f"- Name: {escape_html(session_name)}\n" if session_name else ""

        model_buttons = [
            InlineKeyboardButton(profile.button_label, callback_data=f"sess:model:{profile.key}:{full_session_id}")
            for profile in get_provider_profiles(provider)
        ]
        keyboard = [
            model_buttons,
            [
                InlineKeyboardButton("✏️ Rename", callback_data=f"sess:rename:{full_session_id}"),
                InlineKeyboardButton("📜 History", callback_data=f"sess:history:{full_session_id}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"sess:delete:{full_session_id}"),
            ],
            [
                InlineKeyboardButton("📋 Session List", callback_data="sess:list"),
                InlineKeyboardButton("Switch AI", callback_data="ai:open"),
            ]
        ]

        await query.edit_message_text(
            text=f"✅ <b>Session switched!</b>\n\n"
                 f"- AI: {get_provider_label(provider)}\n"
                 f"- ID: <code>{short_id}</code>\n"
                 f"{name_line}"
                 f"- Model: {model_emoji} {get_profile_label(provider, model)}\n"
                 f"- Messages: {count}\n\n"
                 f"<b>History</b> (last 10)\n{history_text}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    async def _handle_delete_session_confirm(self, query, chat_id: int, session_id: str) -> None:
        """Handle session delete confirmation."""
        user_id = str(chat_id)
        session = self.sessions.get_session_by_prefix(user_id, session_id[:8])
        if not session:
            await query.edit_message_text("❌ Session not found.")
            return

        full_session_id = session.get("full_session_id", session_id)
        short_id = full_session_id[:8]
        name = session.get("name") or f"Session {short_id}"

        current_session_id = self.sessions.get_current_session_id(user_id)
        if current_session_id == full_session_id:
            keyboard = [[InlineKeyboardButton("Back", callback_data="sess:list")]]
            await query.edit_message_text(
                text=f"<b>Cannot Delete</b>\n\n"
                     f"<b>{escape_html(name)}</b> is currently in use.\n\n"
                     f"Switch to another session before deleting.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return

        keyboard = [
            [
                InlineKeyboardButton("Delete", callback_data=f"sess:confirm_del:{full_session_id}"),
                InlineKeyboardButton("Cancel", callback_data="sess:cancel"),
            ]
        ]

        await query.edit_message_text(
            text=f"<b>Delete Session Confirmation</b>\n\n"
                 f"<b>{escape_html(name)}</b>\n"
                 f"ID: <code>{short_id}</code>\n\n"
                 f"Are you sure?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    async def _handle_delete_session_execute(self, query, chat_id: int, session_id: str) -> None:
        """Execute session deletion."""
        user_id = str(chat_id)
        session = self.sessions.get_session_by_prefix(user_id, session_id[:8])
        if not session:
            await query.edit_message_text("❌ Session not found.")
            return

        full_session_id = session.get("full_session_id", session_id)
        short_id = full_session_id[:8]
        name = session.get("name") or f"Session {short_id}"

        current_session_id = self.sessions.get_current_session_id(user_id)
        if current_session_id == full_session_id:
            keyboard = [[InlineKeyboardButton("Back", callback_data="sess:list")]]
            await query.edit_message_text(
                text=f"<b>Cannot Delete</b>\n\n"
                     f"<b>{escape_html(name)}</b> is currently in use.\n\n"
                     f"Switch to another session before deleting.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return

        self.sessions.delete_session(user_id, full_session_id)

        await self._handle_session_list_callback(query, chat_id, f"<s>{escape_html(name)}</s> deleted!\n\n")

    async def _handle_history_callback(self, query, chat_id: int, session_id: str) -> None:
        """Handle session history callback."""
        user_id = str(chat_id)
        session = self.sessions.get_session_by_prefix(user_id, session_id[:8])
        if not session:
            await query.edit_message_text("❌ Session not found.")
            return

        full_session_id = session.get("full_session_id", session_id)
        short_id = full_session_id[:8]
        name = session.get("name") or f"Session {short_id}"
        history = self.sessions.get_session_history_entries(full_session_id)

        lines = [f"<b>{escape_html(name)}</b> History\n"]

        if not history:
            lines.append("(no history)")
        else:
            for i, entry in enumerate(history[-10:], 1):
                msg = entry.get("message", "")[:50] if isinstance(entry, dict) else str(entry)[:50]
                if len(entry.get("message", "") if isinstance(entry, dict) else str(entry)) > 50:
                    msg += "..."
                lines.append(f"{i}. {escape_html(msg)}")

        keyboard = [
            [
                InlineKeyboardButton("Switch", callback_data=f"sess:switch:{full_session_id}"),
                InlineKeyboardButton("List", callback_data="sess:list"),
            ]
        ]

        await query.edit_message_text(
            text="\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    async def _handle_session_list_callback(self, query, chat_id: int, prefix: str = "") -> None:
        """Handle session list callback."""
        user_id = str(chat_id)
        provider = self._get_selected_ai_provider(user_id)
        provider_label = get_provider_label(provider)
        sessions = self.sessions.list_sessions(user_id, ai_provider=provider)
        current_session_id = self.sessions.get_current_session_id(user_id, provider)

        timestamp = datetime.now().strftime("%H:%M:%S")
        lines = [f"{prefix}<b>Session List - {provider_label}</b> <i>({timestamp})</i>\n"]
        buttons = []

        if not sessions:
            lines.append("No sessions.")
        else:
            for session in sessions[:10]:
                sid = session["full_session_id"]
                short_id = session["session_id"]
                name = session.get("name") or f"Session {short_id}"
                model = session.get("model", "sonnet")
                model_badge = get_model_badge(model)
                model_label = get_profile_short_label(provider, model)

                is_current = "> " if sid == current_session_id else ""
                is_locked = self._is_session_locked(sid)
                lock_indicator = " 🔒" if is_locked else ""
                lines.append(
                    f"{is_current}{model_badge} <b>{escape_html(name)}</b> "
                    f"({model_label}, <code>{short_id}</code>){lock_indicator}"
                )

                buttons.append([
                    InlineKeyboardButton(f"{name[:10]}", callback_data=f"sess:switch:{sid}"),
                    InlineKeyboardButton("History", callback_data=f"sess:history:{sid}"),
                    InlineKeyboardButton("Del", callback_data=f"sess:delete:{sid}"),
                ])

        buttons.append(self._build_model_buttons(provider, "sess:new:"))
        buttons.append([
            InlineKeyboardButton("Refresh", callback_data="sess:list"),
            InlineKeyboardButton("Tasks", callback_data="tasks:refresh"),
        ])
        buttons.append([
            InlineKeyboardButton("Switch AI", callback_data="ai:open"),
        ])

        await query.edit_message_text(
            text="\n".join(lines),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )

    async def _handle_model_change_callback(self, query, chat_id: int, model: str, session_id: str) -> None:
        """Handle model change callback."""
        user_id = str(chat_id)
        session = self.sessions.get_session_by_prefix(user_id, session_id[:8])
        if not session:
            await query.edit_message_text("❌ Session not found.")
            return

        full_session_id = session.get("full_session_id", session_id)
        provider = session.get("ai_provider", self._get_selected_ai_provider(user_id))
        if not is_supported_model(provider, model):
            await query.edit_message_text("❌ Unsupported model for this AI.")
            return

        self.sessions.update_session_model(full_session_id, model)

        short_id = full_session_id[:8]
        name = session.get("name") or f"Session {short_id}"
        model_emoji = get_model_emoji(model)

        model_buttons = [
            InlineKeyboardButton(profile.button_label, callback_data=f"sess:model:{profile.key}:{full_session_id}")
            for profile in get_provider_profiles(provider)
        ]
        keyboard = [
            model_buttons,
            [
                InlineKeyboardButton("Session List", callback_data="sess:list"),
            ]
        ]

        await query.edit_message_text(
            text=f"Model changed!\n\n"
                 f"<b>{escape_html(name)}</b>\n"
                 f"AI: <b>{get_provider_label(provider)}</b>\n"
                 f"{model_emoji} Model: <b>{get_profile_label(provider, model)}</b>\n"
                 f"ID: <code>{short_id}</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
