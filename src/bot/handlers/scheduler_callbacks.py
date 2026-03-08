"""Scheduler-related callback handlers."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes

from src.ai import (
    get_default_model,
    get_profile_label,
    get_provider_button,
    get_provider_label,
    get_provider_profiles,
    is_supported_model,
)
from src.logging_config import logger
from src.constants import AVAILABLE_HOURS
from ..formatters import escape_html
from .base import BaseHandler


class SchedulerCallbackHandlers(BaseHandler):
    """Scheduler callback handlers (sched: prefix)."""

    def _build_scheduler_keyboard(self, user_id: str) -> list:
        """Build scheduler UI keyboard - schedule list."""
        buttons = []
        provider = self._get_selected_ai_provider(user_id)

        if self._schedule_manager:
            schedules = self._schedule_manager.list_by_user(user_id)
            for s in sorted(schedules, key=lambda x: (x.hour, x.minute)):
                status = "✅" if s.enabled else "⏸"
                type_icon = "🔌" if s.type == "plugin" else ("📂" if s.type == "workspace" else "💬")
                buttons.append([
                    InlineKeyboardButton(
                        f"{status} {s.time_str} {type_icon} {s.name[:15]}",
                        callback_data=f"sched:detail:{s.id}"
                    ),
                ])

        buttons.append([
            InlineKeyboardButton(f"+ {get_provider_button(provider)}", callback_data="sched:add:claude"),
            InlineKeyboardButton("+ Workspace", callback_data="sched:add:workspace"),
            InlineKeyboardButton("+ Plugin", callback_data="sched:add:plugin"),
        ])
        buttons.append([
            InlineKeyboardButton("Refresh", callback_data="sched:refresh"),
        ])

        return buttons

    async def _handle_schedule_force_reply(self, update, chat_id: int, message: str) -> None:
        """Handle schedule message input ForceReply response."""
        user_id = str(chat_id)
        pending = self._sched_pending.get(user_id)

        if not pending:
            await update.message.reply_text("Schedule input expired. Please try again.")
            return

        if not self._schedule_manager:
            await update.message.reply_text("Schedule feature disabled.")
            del self._sched_pending[user_id]
            return

        schedule_type = pending.get("type", "claude")
        workspace_path = pending.get("workspace_path") if schedule_type == "workspace" else None
        name = pending.get("name", "Schedule")
        model = pending.get("model", "sonnet")
        ai_provider = pending.get("ai_provider", self._get_selected_ai_provider(user_id))

        if schedule_type == "claude" and name == "Schedule":
            name = message[:15].strip() + ("..." if len(message) > 15 else "")

        schedule = self._schedule_manager.add(
            user_id=user_id,
            chat_id=chat_id,
            name=name,
            hour=pending["hour"],
            minute=pending.get("minute", 0),
            message=message,
            schedule_type=schedule_type,
            ai_provider=ai_provider,
            model=model,
            workspace_path=workspace_path,
        )

        del self._sched_pending[user_id]

        keyboard = [[
            InlineKeyboardButton("Schedule List", callback_data="sched:refresh"),
        ]]

        type_label = "workspace" if schedule_type == "workspace" else "schedule"
        path_info = f"\nPath: <code>{escape_html(workspace_path)}</code>" if workspace_path else ""

        await update.message.reply_text(
            f"<b>Schedule Registered!</b>\n\n"
            f"{schedule.type_emoji} <b>{escape_html(schedule.name)}</b> ({type_label})\n"
            f"Time: <b>{schedule.time_str}</b> (daily)\n"
            f"AI: <b>{get_provider_label(ai_provider)}</b>\n"
            f"Model: <b>{get_profile_label(ai_provider, model)}</b>{path_info}\n"
            f"Message: <i>{escape_html(message[:50])}{'...' if len(message) > 50 else ''}</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        logger.info(f"Schedule registered: {schedule.name} @ {schedule.time_str} (type={schedule_type})")

    async def _handle_scheduler_callback(self, query, chat_id: int, callback_data: str) -> None:
        """Handle scheduler callbacks."""
        user_id = str(chat_id)
        action = callback_data[6:]  # Remove "sched:"

        if not self._schedule_manager:
            await query.answer("Schedule feature disabled")
            return

        # Refresh
        if action == "refresh":
            from src.scheduler_manager import scheduler_manager

            provider = self._get_selected_ai_provider(user_id)
            text = (
                f"<b>Scheduler</b>\n"
                f"Current AI: <b>{get_provider_label(provider)}</b>\n\n"
                f"{self._schedule_manager.get_status_text(user_id)}"
            )
            text += scheduler_manager.get_system_jobs_text()
            keyboard = self._build_scheduler_keyboard(user_id)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            await query.answer("Refreshed")
            return

        # Toggle
        if action.startswith("toggle:"):
            from src.scheduler_manager import scheduler_manager

            schedule_id = action[7:]
            new_state = self._schedule_manager.toggle(schedule_id)
            if new_state is not None:
                status = "ON" if new_state else "OFF"
                await query.answer(f"{status}")
                # Return to detail view
                await self._handle_scheduler_callback(query, chat_id, f"sched:detail:{schedule_id}")
            else:
                await query.answer("Schedule not found")
            return

        # Delete
        if action.startswith("delete:"):
            from src.scheduler_manager import scheduler_manager

            schedule_id = action[7:]
            if self._schedule_manager.remove(schedule_id):
                await query.answer("Deleted")
                provider = self._get_selected_ai_provider(user_id)
                text = (
                    f"<b>Scheduler</b>\n"
                    f"Current AI: <b>{get_provider_label(provider)}</b>\n\n"
                    f"{self._schedule_manager.get_status_text(user_id)}"
                )
                text += scheduler_manager.get_system_jobs_text()
                keyboard = self._build_scheduler_keyboard(user_id)
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            else:
                await query.answer("Delete failed")
            return

        # Schedule detail view
        if action.startswith("detail:"):
            schedule_id = action[7:]
            schedule = self._schedule_manager.get(schedule_id)
            if not schedule:
                await query.answer("Schedule not found")
                return

            status_text = "ON" if schedule.enabled else "OFF"
            toggle_label = "⏸ OFF" if schedule.enabled else "✅ ON"
            path_info = f"\nPath: <code>{escape_html(schedule.workspace_path)}</code>" if schedule.workspace_path else ""

            buttons = [
                [InlineKeyboardButton(toggle_label, callback_data=f"sched:toggle:{schedule_id}")],
                [InlineKeyboardButton(f"⏰ Change Time ({schedule.time_str})", callback_data=f"sched:chtime:{schedule_id}")],
                [InlineKeyboardButton("🗑 Delete", callback_data=f"sched:delete:{schedule_id}")],
                [InlineKeyboardButton("← Back", callback_data="sched:refresh")],
            ]

            await query.edit_message_text(
                f"{schedule.type_emoji} <b>{escape_html(schedule.name)}</b>\n\n"
                f"Status: <b>{status_text}</b>\n"
                f"Time: <b>{schedule.time_str}</b> (daily)\n"
                f"AI: <b>{get_provider_label(schedule.ai_provider)}</b>\n"
                f"Model: <b>{get_profile_label(schedule.ai_provider, schedule.model)}</b> "
                f"(<code>{schedule.model}</code>){path_info}\n"
                f"Message: <i>{escape_html(schedule.message[:80])}{'...' if len(schedule.message) > 80 else ''}</i>\n"
                f"Runs: {schedule.run_count}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Change time - hour selection
        if action.startswith("chtime:"):
            schedule_id = action[7:]
            schedule = self._schedule_manager.get(schedule_id)
            if not schedule:
                await query.answer("Schedule not found")
                return

            buttons = []
            row = []
            for hour in AVAILABLE_HOURS:
                row.append(InlineKeyboardButton(
                    f"{hour:02d}h",
                    callback_data=f"sched:chtime_hour:{schedule_id}:{hour}"
                ))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            await query.edit_message_text(
                f"<b>Change Time</b>\n\n"
                f"{schedule.type_emoji} <b>{escape_html(schedule.name)}</b>\n"
                f"Current: <b>{schedule.time_str}</b>\n\n"
                f"Select new hour:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Change time - minute selection
        if action.startswith("chtime_hour:"):
            parts = action[12:].split(":")
            schedule_id, hour = parts[0], int(parts[1])

            buttons = []
            row = []
            for minute in range(0, 60, 5):
                row.append(InlineKeyboardButton(
                    f":{minute:02d}",
                    callback_data=f"sched:chtime_min:{schedule_id}:{hour}:{minute}"
                ))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            await query.edit_message_text(
                f"<b>Change Time</b>\n\n"
                f"New hour: <b>{hour:02d}h</b>\n\n"
                f"Select minute:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Change time - apply
        if action.startswith("chtime_min:"):
            from src.scheduler_manager import scheduler_manager

            parts = action[11:].split(":")
            schedule_id, hour, minute = parts[0], int(parts[1]), int(parts[2])

            result = self._schedule_manager.update_time(schedule_id, hour, minute)
            if result:
                await query.answer(f"Changed to {hour:02d}:{minute:02d}")
            else:
                await query.answer("Update failed")

            provider = self._get_selected_ai_provider(user_id)
            text = (
                f"<b>Scheduler</b>\n"
                f"Current AI: <b>{get_provider_label(provider)}</b>\n\n"
                f"{self._schedule_manager.get_status_text(user_id)}"
            )
            text += scheduler_manager.get_system_jobs_text()
            keyboard = self._build_scheduler_keyboard(user_id)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            return

        # Add - current AI type (time selection)
        if action in ("add:ai", "add:claude"):
            provider = self._get_selected_ai_provider(user_id)
            buttons = []
            row = []
            for hour in AVAILABLE_HOURS:
                row.append(InlineKeyboardButton(
                    f"{hour:02d}h",
                    callback_data=f"sched:time:claude:_:{hour}"
                ))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            self._sched_pending[user_id] = {
                "type": "claude",
                "ai_provider": provider,
            }

            await query.edit_message_text(
                f"<b>Add {get_provider_label(provider)} Schedule</b>\n\n"
                f"Regular {get_provider_label(provider)} conversation (new session)\n\n"
                "Select time (daily repeat):",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Add - Workspace type (path selection)
        if action == "add:workspace":
            if not self._workspace_registry:
                await query.answer("Workspace feature not initialized.")
                return

            workspaces = self._workspace_registry.list_by_user(user_id)
            if not workspaces:
                await query.edit_message_text(
                    "<b>No workspaces registered.</b>\n\n"
                    "Register one first at /workspace.",
                    parse_mode="HTML"
                )
                await query.answer()
                return

            buttons = []
            ws_map = {}
            for i, ws in enumerate(workspaces):
                ws_map[i] = {"path": ws.path, "name": ws.name}
                buttons.append([
                    InlineKeyboardButton(
                        f"{ws.name}",
                        callback_data=f"sched:wspath:{i}"
                    )
                ])

            self._sched_pending[user_id] = {
                "workspaces": ws_map,
                "ai_provider": self._get_selected_ai_provider(user_id),
            }

            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            await query.edit_message_text(
                "<b>Add Workspace Schedule</b>\n\n"
                "Select workspace:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Plugin schedule - show plugins with scheduled actions
        if action == "add:plugin":
            if not self.plugins or not self.plugins.plugins:
                await query.edit_message_text(
                    "<b>No plugins loaded.</b>",
                    parse_mode="HTML"
                )
                await query.answer()
                return

            buttons = []
            plugin_map = {}
            idx = 0
            for plugin in self.plugins.plugins:
                actions = plugin.get_scheduled_actions()
                if actions:
                    plugin_map[idx] = {"name": plugin.name, "actions": actions}
                    buttons.append([
                        InlineKeyboardButton(
                            f"🔌 {plugin.name} ({len(actions)} actions)",
                            callback_data=f"sched:plugin:{idx}"
                        )
                    ])
                    idx += 1

            if not buttons:
                await query.edit_message_text(
                    "<b>No schedulable plugins.</b>\n\n"
                    "Implement <code>get_scheduled_actions()</code> in your plugin.",
                    parse_mode="HTML"
                )
                await query.answer()
                return

            self._sched_pending[user_id] = {"plugin_map": plugin_map}
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            await query.edit_message_text(
                "<b>Add Plugin Schedule</b>\n\n"
                "Select plugin:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Plugin selected - show actions
        if action.startswith("plugin:") and not action.startswith("pluginaction:"):
            plugin_idx = int(action[7:])
            pending = self._sched_pending.get(user_id, {})
            plugin_map = pending.get("plugin_map", {})
            plugin_info = plugin_map.get(plugin_idx)

            if not plugin_info:
                await query.answer("Invalid plugin")
                return

            pending["selected_plugin"] = plugin_info["name"]
            self._sched_pending[user_id] = pending

            buttons = []
            for i, act in enumerate(plugin_info["actions"]):
                buttons.append([
                    InlineKeyboardButton(
                        f"{act.description}",
                        callback_data=f"sched:pluginaction:{i}"
                    )
                ])
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            await query.edit_message_text(
                f"<b>🔌 {plugin_info['name']}</b>\n\n"
                f"Select action:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Plugin action selected - time selection
        if action.startswith("pluginaction:"):
            action_idx = int(action[13:])
            pending = self._sched_pending.get(user_id, {})
            plugin_name = pending.get("selected_plugin")
            plugin_map = pending.get("plugin_map", {})

            # Find the plugin's actions
            actions = []
            for info in plugin_map.values():
                if info["name"] == plugin_name:
                    actions = info["actions"]
                    break

            if action_idx >= len(actions):
                await query.answer("Invalid action")
                return

            selected_action = actions[action_idx]
            pending["type"] = "plugin"
            pending["plugin_name"] = plugin_name
            pending["action_name"] = selected_action.name
            pending["name"] = f"{plugin_name}:{selected_action.description}"
            self._sched_pending[user_id] = pending

            buttons = []
            row = []
            for hour in AVAILABLE_HOURS:
                row.append(InlineKeyboardButton(
                    f"{hour:02d}h",
                    callback_data=f"sched:time:plugin:_:{hour}"
                ))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            await query.edit_message_text(
                f"<b>Add Plugin Schedule</b>\n\n"
                f"🔌 <b>{plugin_name}</b> - {selected_action.description}\n\n"
                f"Select time (daily repeat):",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Workspace selected - time selection
        if action.startswith("wspath:"):
            ws_idx = int(action[7:])
            pending = self._sched_pending.get(user_id, {})
            ws_map = pending.get("workspaces", {})

            ws_info = ws_map.get(ws_idx)
            if not ws_info:
                await query.answer("Invalid workspace")
                return

            workspace_path = ws_info["path"]
            workspace_name = ws_info["name"]
            path_idx = ws_idx

            buttons = []
            row = []
            for hour in AVAILABLE_HOURS:
                row.append(InlineKeyboardButton(
                    f"{hour:02d}h",
                    callback_data=f"sched:time:workspace:{path_idx}:{hour}"
                ))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            await query.edit_message_text(
                f"<b>Add Workspace Schedule</b>\n\n"
                f"Workspace: <b>{workspace_name}</b>\n"
                f"<code>{workspace_path}</code>\n\n"
                f"Select time (daily repeat):",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Time (hour) selected - minute selection
        if action.startswith("time:"):
            parts = action[5:].split(":")
            if len(parts) != 3:
                await query.answer("Invalid request")
                return

            schedule_type, path_idx, hour = parts[0], parts[1], int(parts[2])

            pending = self._sched_pending.get(user_id, {})
            pending["type"] = schedule_type
            pending["hour"] = hour
            pending.setdefault("ai_provider", self._get_selected_ai_provider(user_id))

            if schedule_type == "workspace" and path_idx != "_":
                ws_map = pending.get("workspaces", {})
                idx = int(path_idx)
                ws_info = ws_map.get(idx)
                if ws_info:
                    pending["workspace_path"] = ws_info["path"]
                    pending["name"] = ws_info["name"]

            self._sched_pending[user_id] = pending

            # Minute selection buttons (00~55, 5-min intervals)
            buttons = []
            row = []
            for minute in range(0, 60, 5):
                row.append(InlineKeyboardButton(
                    f":{minute:02d}",
                    callback_data=f"sched:minute:{minute}"
                ))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([
                InlineKeyboardButton("Cancel", callback_data="sched:refresh")
            ])

            type_label = "Workspace" if schedule_type == "workspace" else f"{get_provider_label(pending['ai_provider'])} Schedule"
            path_info = f"\nPath: <code>{pending.get('workspace_path', '')}</code>" if schedule_type == "workspace" else ""

            await query.edit_message_text(
                f"<b>Add {type_label} Schedule</b>\n\n"
                f"Hour: <b>{hour:02d}h</b>{path_info}\n\n"
                f"Select minute:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Minute selected - model selection (or direct register for plugin)
        if action.startswith("minute:"):
            minute = int(action[7:])

            pending = self._sched_pending.get(user_id, {})
            pending["minute"] = minute
            self._sched_pending[user_id] = pending

            hour = pending.get("hour", 9)
            schedule_type = pending.get("type", "claude")
            ai_provider = pending.get("ai_provider", self._get_selected_ai_provider(user_id))

            # Plugin type: skip model/message, register directly
            if schedule_type == "plugin":
                if not self._schedule_manager:
                    await query.edit_message_text("Schedule feature disabled.")
                    del self._sched_pending[user_id]
                    return

                schedule = self._schedule_manager.add(
                    user_id=user_id,
                    chat_id=chat_id,
                    name=pending.get("name", "Plugin Schedule"),
                    hour=hour,
                    minute=minute,
                    message="",  # plugin doesn't need message
                    schedule_type="plugin",
                    ai_provider=ai_provider,
                    model="sonnet",  # unused for plugin
                    plugin_name=pending.get("plugin_name"),
                    action_name=pending.get("action_name"),
                )

                del self._sched_pending[user_id]

                keyboard = [[
                    InlineKeyboardButton("Schedule List", callback_data="sched:refresh"),
                ]]

                await query.edit_message_text(
                    f"<b>Plugin Schedule Registered!</b>\n\n"
                    f"🔌 <b>{schedule.name}</b>\n"
                    f"Time: <b>{schedule.time_str}</b> (daily)\n"
                    f"Plugin: <b>{schedule.plugin_name}</b>\n"
                    f"Action: <b>{schedule.action_name}</b>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
                logger.info(f"Plugin schedule registered: {schedule.name} @ {schedule.time_str}")
                return

            buttons = [
                self._build_model_buttons(ai_provider, "sched:model:"),
                [InlineKeyboardButton("Cancel", callback_data="sched:refresh")],
            ]

            type_label = "Workspace" if schedule_type == "workspace" else f"{get_provider_label(ai_provider)} Schedule"
            path_info = f"\nPath: <code>{pending.get('workspace_path', '')}</code>" if schedule_type == "workspace" else ""

            await query.edit_message_text(
                f"<b>Add {type_label} Schedule</b>\n\n"
                f"Time: <b>{hour:02d}:{minute:02d}</b>{path_info}\n\n"
                f"Select model:",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
            await query.answer()
            return

        # Model selected - message input (ForceReply)
        if action.startswith("model:"):
            model = action[6:]
            pending = self._sched_pending.get(user_id, {})
            ai_provider = pending.get("ai_provider", self._get_selected_ai_provider(user_id))
            if not is_supported_model(ai_provider, model):
                await query.edit_message_text("❌ Unsupported model for the selected AI.")
                return
            pending["model"] = model
            self._sched_pending[user_id] = pending

            schedule_type = pending.get("type", "claude")
            hour = pending.get("hour", 9)
            minute = pending.get("minute", 0)
            type_label = "Workspace" if schedule_type == "workspace" else f"{get_provider_label(ai_provider)} Schedule"
            path_info = f"\nPath: <code>{pending.get('workspace_path', '')}</code>" if schedule_type == "workspace" else ""

            await query.edit_message_text(
                f"<b>Add {type_label} Schedule</b>\n\n"
                f"Time: <b>{hour:02d}:{minute:02d}</b>\n"
                f"AI: <b>{get_provider_label(ai_provider)}</b>\n"
                f"Model: <b>{get_profile_label(ai_provider, model)}</b> (<code>{model}</code>){path_info}\n\n"
                f"Enter scheduled message below:",
                parse_mode="HTML"
            )

            await query.message.reply_text(
                "Enter scheduled message (schedule_input):",
                reply_markup=ForceReply(selective=True, input_field_placeholder="e.g., Summarize today's tasks")
            )
            await query.answer()
            return

        await query.answer("Unknown action")
