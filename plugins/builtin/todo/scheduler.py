"""Todo 스케줄러 - 시간대별 리마인더 관리."""

from datetime import datetime, time
from typing import Optional, TYPE_CHECKING
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.logging_config import logger
from src.scheduler_manager import scheduler_manager

if TYPE_CHECKING:
    from telegram.ext import Application

from .manager import TodoManager, TimeSlot


# 한국 시간대
KST = ZoneInfo("Asia/Seoul")

# 스케줄 시간 설정
SCHEDULE_TIMES = {
    "morning_wrap": time(8, 0, tzinfo=KST),     # 08:00 KST - 어제 미완료 → 오늘로 이관
    "morning_check": time(10, 0, tzinfo=KST),   # 10:00 KST - 오전 할일 리마인더
    "afternoon_check": time(15, 0, tzinfo=KST), # 15:00 KST - 오후 할일 리마인더
    "evening_check": time(19, 0, tzinfo=KST),   # 19:00 KST - 저녁 할일 리마인더
    "daily_wrap": time(21, 0, tzinfo=KST),      # 21:00 KST - 하루 마무리
}


class TodoScheduler:
    """할일 스케줄러 (버튼 기반)."""

    OWNER = "TodoScheduler"

    def __init__(
        self,
        todo_manager: TodoManager,
        chat_ids: list[int],
    ):
        """
        Args:
            todo_manager: 할일 관리자
            chat_ids: 알림 받을 채팅 ID 목록
        """
        self.manager = todo_manager
        self.chat_ids = chat_ids
        self._app: Optional["Application"] = None

    def set_app(self, app: "Application") -> None:
        """텔레그램 앱 설정."""
        self._app = app

    def register_chat_id(self, chat_id: int) -> None:
        """채팅 ID 등록."""
        if chat_id not in self.chat_ids:
            self.chat_ids.append(chat_id)
            logger.info(f"Todo 스케줄러에 chat_id 등록: {chat_id}")

    def setup_jobs(self, app: "Application") -> None:
        """스케줄 작업 설정 (SchedulerManager 사용)."""
        self._app = app

        # 기존 작업 제거
        scheduler_manager.unregister_by_owner(self.OWNER)

        # 08:00 - 아침 마무리 (어제 미완료 → 오늘 이관)
        scheduler_manager.register_daily(
            name="todo_morning_wrap",
            callback=self._morning_wrap_callback,
            time_of_day=SCHEDULE_TIMES["morning_wrap"],
            owner=self.OWNER,
            metadata={"slot": "morning_wrap"},
        )
        logger.info("스케줄 등록: 08:00 아침 마무리 (via SchedulerManager)")

        # 10:00 - 오전 할일 체크
        scheduler_manager.register_daily(
            name="todo_morning_check",
            callback=self._morning_check_callback,
            time_of_day=SCHEDULE_TIMES["morning_check"],
            owner=self.OWNER,
            metadata={"slot": "morning"},
        )
        logger.info("스케줄 등록: 10:00 오전 할일 리마인더 (via SchedulerManager)")

        # 15:00 - 오후 할일 체크
        scheduler_manager.register_daily(
            name="todo_afternoon_check",
            callback=self._afternoon_check_callback,
            time_of_day=SCHEDULE_TIMES["afternoon_check"],
            owner=self.OWNER,
            metadata={"slot": "afternoon"},
        )
        logger.info("스케줄 등록: 15:00 오후 할일 리마인더 (via SchedulerManager)")

        # 19:00 - 저녁 할일 체크
        scheduler_manager.register_daily(
            name="todo_evening_check",
            callback=self._evening_check_callback,
            time_of_day=SCHEDULE_TIMES["evening_check"],
            owner=self.OWNER,
            metadata={"slot": "evening"},
        )
        logger.info("스케줄 등록: 19:00 저녁 할일 리마인더 (via SchedulerManager)")

        # 21:00 - 하루 마무리
        scheduler_manager.register_daily(
            name="todo_daily_wrap",
            callback=self._daily_wrap_callback,
            time_of_day=SCHEDULE_TIMES["daily_wrap"],
            owner=self.OWNER,
            metadata={"slot": "wrap"},
        )
        logger.info("스케줄 등록: 21:00 하루 마무리 (via SchedulerManager)")

        job_count = len(scheduler_manager.list_jobs_by_owner(self.OWNER))
        logger.info(f"Todo 스케줄러 설정 완료 - {job_count}개 작업 (via SchedulerManager)")

    async def _morning_wrap_callback(self, context) -> None:
        """08:00 - 아침 마무리 (어제 미완료 → 오늘 이관)."""
        from datetime import timedelta

        logger.info("아침 마무리 알림 시작")

        for chat_id in self._get_active_chat_ids():
            try:
                # 어제 날짜 계산
                yesterday = datetime.now(KST).date() - timedelta(days=1)
                yesterday_daily = self.manager.get_daily_by_date(chat_id, yesterday)

                if not yesterday_daily:
                    continue  # 어제 데이터 없으면 스킵

                all_tasks = yesterday_daily.get_all_tasks()
                pending = []
                for slot_value, tasks in all_tasks.items():
                    for t in tasks:
                        if not t.done:
                            pending.append((slot_value, t))

                if not pending:
                    continue  # 어제 미완료 없으면 스킵

                # 메시지 구성
                lines = ["☀️ <b>아침 마무리</b>\n"]
                lines.append(f"어제 미완료 항목이 {len(pending)}개 있어요:\n")

                slot_names = {
                    TimeSlot.MORNING.value: "🌅 오전",
                    TimeSlot.AFTERNOON.value: "☀️ 오후",
                    TimeSlot.EVENING.value: "🌙 저녁",
                }

                for slot_value, task in pending:
                    slot_name = slot_names.get(slot_value, slot_value)
                    lines.append(f"  ⬜ [{slot_name}] {task.text}")

                lines.append("\n오늘로 이관할 항목을 선택하세요:")

                # 버튼 구성
                buttons = [
                    [
                        InlineKeyboardButton("🔄 전체 이관", callback_data="td:carry_all"),
                        InlineKeyboardButton("📋 선택 이관", callback_data="td:multi"),
                    ],
                    [
                        InlineKeyboardButton("🗑 전체 삭제", callback_data="td:clear_yesterday"),
                        InlineKeyboardButton("📄 오늘 리스트", callback_data="td:list"),
                    ],
                ]

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="\n".join(lines),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                logger.info(f"아침 마무리 알림 전송: chat_id={chat_id}, pending={len(pending)}")

            except Exception as e:
                logger.error(f"아침 마무리 알림 실패: chat_id={chat_id}, error={e}")

    async def _morning_check_callback(self, context) -> None:
        """10:00 - 오전 할일 체크."""
        await self._send_slot_reminder(context, TimeSlot.MORNING, "🌅 오전")

    async def _afternoon_check_callback(self, context) -> None:
        """15:00 - 오후 할일 체크."""
        await self._send_slot_reminder(context, TimeSlot.AFTERNOON, "☀️ 오후")

    async def _evening_check_callback(self, context) -> None:
        """19:00 - 저녁 할일 체크."""
        await self._send_slot_reminder(context, TimeSlot.EVENING, "🌙 저녁")

    async def _daily_wrap_callback(self, context) -> None:
        """21:00 - 하루 마무리."""
        logger.info("하루 마무리 알림 시작")

        for chat_id in self._get_active_chat_ids():
            try:
                daily = self.manager.get_today(chat_id)
                all_tasks = daily.get_all_tasks()

                # 통계 계산
                total = sum(len(tasks) for tasks in all_tasks.values())
                done = sum(1 for tasks in all_tasks.values() for t in tasks if t.done)
                pending = total - done

                if total == 0:
                    continue  # 할일 없으면 스킵

                # 메시지 구성
                lines = ["🌙 <b>하루 마무리</b>\n"]

                if pending == 0:
                    lines.append("🎉 오늘 할일을 모두 완료했어요!")
                else:
                    lines.append(f"📊 오늘 진행률: {done}/{total} 완료\n")
                    lines.append("<b>미완료 항목:</b>")

                    slot_names = {
                        TimeSlot.MORNING.value: "🌅 오전",
                        TimeSlot.AFTERNOON.value: "☀️ 오후",
                        TimeSlot.EVENING.value: "🌙 저녁",
                    }

                    for slot_value, tasks in all_tasks.items():
                        pending_tasks = [t for t in tasks if not t.done]
                        if pending_tasks:
                            slot_name = slot_names.get(slot_value, slot_value)
                            lines.append(f"\n{slot_name}")
                            for t in pending_tasks:
                                lines.append(f"  ⬜ {t.text}")

                    lines.append("\n내일로 넘길 항목이 있나요?")

                # 버튼 구성
                buttons = []
                if pending > 0:
                    buttons.append([
                        InlineKeyboardButton("📋 멀티 선택", callback_data="td:multi"),
                        InlineKeyboardButton("🔄 전체 넘기기", callback_data="td:carry_all"),
                    ])
                buttons.append([
                    InlineKeyboardButton("✅ 오늘 마무리", callback_data="td:wrap_done"),
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

    async def _send_slot_reminder(self, context, slot: TimeSlot, slot_name: str) -> None:
        """시간대별 리마인더 전송 (버튼 포함)."""
        logger.info(f"{slot_name} 할일 리마인더 시작")

        for chat_id in self._get_active_chat_ids():
            try:
                daily = self.manager.get_today(chat_id)
                tasks = daily.get_tasks(slot)

                if not tasks:
                    # 할일이 없으면 스킵
                    continue

                pending = [t for t in tasks if not t.done]
                if not pending:
                    # 모두 완료됨
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"{slot_name} 할일 모두 완료! 👏",
                        parse_mode="HTML"
                    )
                    continue

                # 미완료 할일 알림
                lines = [f"<b>{slot_name} 할일 리마인더</b>\n"]
                for i, task in enumerate(tasks, 1):
                    status = "✅" if task.done else "⬜"
                    lines.append(f"{status} {i}. {task.text}")

                lines.append(f"\n📊 {len(tasks) - len(pending)}/{len(tasks)} 완료")

                # 버튼 추가
                keyboard = [
                    [
                        InlineKeyboardButton("📄 리스트 열기", callback_data="td:list"),
                        InlineKeyboardButton("➕ 추가", callback_data="td:add"),
                    ]
                ]

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="\n".join(lines),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.info(f"{slot_name} 리마인더 전송: chat_id={chat_id}")

            except Exception as e:
                logger.error(f"{slot_name} 리마인더 실패: chat_id={chat_id}, error={e}")

    def _get_active_chat_ids(self) -> list[int]:
        """활성 채팅 ID 목록 (등록된 + 오늘 데이터 있는)."""
        registered = set(self.manager.get_registered_chat_ids())
        configured = set(self.chat_ids)
        return list(registered | configured)

    async def send_immediate_reminder(self, chat_id: int) -> str:
        """즉시 리마인더 전송 (테스트용)."""
        return self.manager.get_daily_summary(chat_id)

    def get_next_schedules(self) -> list[dict]:
        """다음 스케줄 목록."""
        now = datetime.now(KST)
        schedules = []

        for name, scheduled_time in SCHEDULE_TIMES.items():
            scheduled_dt = datetime.combine(now.date(), scheduled_time, tzinfo=KST)
            if scheduled_dt < now:
                # 이미 지났으면 다음 날
                from datetime import timedelta
                scheduled_dt += timedelta(days=1)

            schedules.append({
                "name": name,
                "time": scheduled_time.strftime("%H:%M"),
                "next": scheduled_dt.isoformat(),
            })

        return sorted(schedules, key=lambda x: x["next"])
