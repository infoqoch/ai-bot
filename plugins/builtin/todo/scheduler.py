"""Todo 스케줄러 - Repository 기반 시간대별 리마인더."""

from datetime import datetime, date, time, timedelta
from typing import Optional, TYPE_CHECKING
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.logging_config import logger
from src.scheduler_manager import scheduler_manager

if TYPE_CHECKING:
    from telegram.ext import Application
    from src.repository import Repository

KST = ZoneInfo("Asia/Seoul")

SCHEDULE_TIMES = {
    "morning_check": time(10, 0, tzinfo=KST),
    "afternoon_check": time(15, 0, tzinfo=KST),
    "evening_check": time(19, 0, tzinfo=KST),
    "daily_wrap": time(21, 0, tzinfo=KST),
}

SLOTS = ["morning", "afternoon", "evening"]
SLOT_NAMES = {
    "morning": "🌅 오전",
    "afternoon": "☀️ 오후",
    "evening": "🌙 저녁",
}


class TodoScheduler:
    """Repository 기반 할일 스케줄러."""

    OWNER = "TodoScheduler"

    def __init__(self, repository: "Repository", chat_ids: list[int]):
        self.repository = repository
        self.chat_ids = chat_ids
        self._app: Optional["Application"] = None

    def setup_jobs(self, app: "Application") -> None:
        """스케줄 작업 설정."""
        self._app = app
        scheduler_manager.unregister_by_owner(self.OWNER)

        scheduler_manager.register_daily(
            name="todo_morning_check",
            callback=self._morning_check_callback,
            time_of_day=SCHEDULE_TIMES["morning_check"],
            owner=self.OWNER,
        )

        scheduler_manager.register_daily(
            name="todo_afternoon_check",
            callback=self._afternoon_check_callback,
            time_of_day=SCHEDULE_TIMES["afternoon_check"],
            owner=self.OWNER,
        )

        scheduler_manager.register_daily(
            name="todo_evening_check",
            callback=self._evening_check_callback,
            time_of_day=SCHEDULE_TIMES["evening_check"],
            owner=self.OWNER,
        )

        scheduler_manager.register_daily(
            name="todo_daily_wrap",
            callback=self._daily_wrap_callback,
            time_of_day=SCHEDULE_TIMES["daily_wrap"],
            owner=self.OWNER,
        )

        logger.info(f"Todo 스케줄러 설정 완료 - {len(SCHEDULE_TIMES)}개 작업")

    def _today(self) -> str:
        return date.today().isoformat()

    async def _morning_check_callback(self, context) -> None:
        await self._send_slot_reminder(context, "morning")

    async def _afternoon_check_callback(self, context) -> None:
        await self._send_slot_reminder(context, "afternoon")

    async def _evening_check_callback(self, context) -> None:
        await self._send_slot_reminder(context, "evening")

    async def _daily_wrap_callback(self, context) -> None:
        """21:00 - 하루 마무리."""
        logger.info("하루 마무리 알림 시작")
        today = self._today()

        for chat_id in self.chat_ids:
            try:
                stats = self.repository.get_todo_stats(chat_id, today)
                if stats["total"] == 0:
                    continue

                lines = ["🌙 <b>하루 마무리</b>\n"]

                if stats["pending"] == 0:
                    lines.append("🎉 오늘 할일을 모두 완료했어요!")
                else:
                    lines.append(f"📊 오늘 진행률: {stats['done']}/{stats['total']} 완료\n")
                    lines.append("<b>미완료 항목:</b>")

                    pending = self.repository.get_pending_todos(chat_id, today)
                    current_slot = None
                    for todo in pending:
                        if todo.slot != current_slot:
                            current_slot = todo.slot
                            lines.append(f"\n{SLOT_NAMES[todo.slot]}")
                        lines.append(f"  ⬜ {todo.text}")

                    lines.append("\n내일로 넘길 항목이 있나요?")

                buttons = []
                if stats["pending"] > 0:
                    buttons.append([
                        InlineKeyboardButton("📋 멀티 선택", callback_data="td:multi"),
                    ])
                buttons.append([
                    InlineKeyboardButton("📄 리스트", callback_data="td:list"),
                ])

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="\n".join(lines),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                logger.info(f"하루 마무리 알림 전송: chat_id={chat_id}")

            except Exception as e:
                logger.error(f"하루 마무리 알림 실패: chat_id={chat_id}, error={e}")

    async def _send_slot_reminder(self, context, slot: str) -> None:
        """시간대별 리마인더."""
        slot_name = SLOT_NAMES[slot]
        logger.info(f"{slot_name} 할일 리마인더 시작")
        today = self._today()

        for chat_id in self.chat_ids:
            try:
                todos = self.repository.list_todos_by_slot(chat_id, today, slot)
                if not todos:
                    continue

                pending = [t for t in todos if not t.done]
                if not pending:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"{slot_name} 할일 모두 완료! 👏",
                        parse_mode="HTML"
                    )
                    continue

                lines = [f"<b>{slot_name} 할일 리마인더</b>\n"]
                for i, todo in enumerate(todos, 1):
                    status = "✅" if todo.done else "⬜"
                    lines.append(f"{status} {i}. {todo.text}")

                lines.append(f"\n📊 {len(todos) - len(pending)}/{len(todos)} 완료")

                keyboard = [[
                    InlineKeyboardButton("📄 리스트 열기", callback_data="td:list"),
                    InlineKeyboardButton("➕ 추가", callback_data="td:add"),
                ]]

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="\n".join(lines),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.info(f"{slot_name} 리마인더 전송: chat_id={chat_id}")

            except Exception as e:
                logger.error(f"{slot_name} 리마인더 실패: chat_id={chat_id}, error={e}")
