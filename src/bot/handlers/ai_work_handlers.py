"""AI Work handlers - contextual AI assistance for each domain."""

import re
from datetime import datetime, timedelta

from telegram import ForceReply
from telegram.ext import ContextTypes

from src.logging_config import logger
from src.time_utils import app_now, get_app_timezone
from src.ui_emoji import BUTTON_AI_WORK
from .base import BaseHandler


DOMAIN_LABELS = {
    "scheduler": "스케줄러",
    "workspace": "워크스페이스",
    "calendar": "캘린더",
    "tasks": "작업 현황",
    "todo": "할일",
    "memo": "메모",
    "weather": "날씨",
    "diary": "일기",
}


class AiWorkHandlers(BaseHandler):
    """Contextual AI assistance - '✨ AI와 작업하기' feature."""

    async def _handle_aiwork_callback(self, query, chat_id: int, callback_data: str) -> None:
        """Handle aiwork:{domain} callback - show ForceReply prompt."""
        domain = callback_data.split(":", 1)[1] if ":" in callback_data else ""
        label = DOMAIN_LABELS.get(domain, domain)

        await query.message.reply_text(
            f"✨ <b>{label} - AI와 작업하기</b>\n\n"
            f"무엇을 도와드릴까요?\n"
            f"<i>현재 {label} 데이터를 AI에게 전달합니다.</i>\n\n"
            f"<code>aiwork:{domain}</code>",
            parse_mode="HTML",
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder=f"{label} 관련 질문을 입력하세요",
            ),
        )

    async def _handle_aiwork_force_reply(
        self, update, chat_id: int, message: str, domain: str
    ) -> None:
        """Gather domain context and dispatch to AI."""
        user_id = str(chat_id)
        label = DOMAIN_LABELS.get(domain, domain)
        context_text = await self._gather_domain_context(chat_id, domain)

        augmented_message = (
            f"[참고 정보 - 현재 {label} 데이터]\n"
            f"{context_text}\n\n"
            f"위 정보를 참고하여 다음 요청에 답해주세요:\n"
            f"{message}"
        )

        await self._dispatch_to_ai(update, chat_id, user_id, augmented_message)

    async def _gather_domain_context(self, chat_id: int, domain: str) -> str:
        """Gather domain-specific context data."""
        gatherers = {
            "scheduler": self._ctx_scheduler,
            "workspace": self._ctx_workspace,
            "calendar": self._ctx_calendar,
            "tasks": self._ctx_tasks,
            "todo": self._ctx_todo,
            "memo": self._ctx_memo,
            "weather": self._ctx_weather,
            "diary": self._ctx_diary,
        }
        gatherer = gatherers.get(domain)
        if not gatherer:
            return "(알 수 없는 도메인)"
        try:
            return await gatherer(chat_id)
        except Exception as e:
            logger.error(f"Context gathering error for {domain}: {e}", exc_info=True)
            return f"(데이터 수집 중 오류: {e})"

    async def _ctx_scheduler(self, chat_id: int) -> str:
        repo = self._repository
        if not repo:
            return "(데이터 없음)"
        schedules = repo.list_schedules_by_user(str(chat_id))
        if not schedules:
            return "등록된 스케줄이 없습니다."
        lines = []
        for s in schedules:
            status = "ON" if s.enabled else "OFF"
            lines.append(f"- [{status}] {s.name} (유형: {s.schedule_type}, 시간: {s.trigger_summary})")
        return "\n".join(lines)

    async def _ctx_workspace(self, chat_id: int) -> str:
        repo = self._repository
        if not repo:
            return "(데이터 없음)"
        workspaces = repo.list_workspaces_by_user(str(chat_id))
        if not workspaces:
            return "등록된 워크스페이스가 없습니다."
        lines = []
        for ws in workspaces:
            lines.append(f"- {ws.name} ({ws.short_path})")
        return "\n".join(lines)

    async def _ctx_calendar(self, chat_id: int) -> str:
        if not self.plugins:
            return "(캘린더 플러그인 없음)"
        cal_plugin = self.plugins.get_plugin_by_name("calendar")
        if not cal_plugin:
            return "(캘린더 플러그인 없음)"
        try:
            gcal = getattr(cal_plugin, '_gcal', None)
            if gcal and getattr(gcal, 'available', False):
                today = app_now()
                start = today.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                events = gcal.list_events(start, end)
                if not events:
                    return "오늘 일정이 없습니다."
                lines = []
                for ev in events:
                    if ev.all_day:
                        time_str = "종일"
                    else:
                        time_str = ev.start.strftime("%H:%M")
                    lines.append(f"- {time_str}: {ev.summary}")
                return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Calendar context error: {e}")
        return "(캘린더 데이터 조회 실패)"

    async def _ctx_tasks(self, chat_id: int) -> str:
        repo = self._repository
        if not repo:
            return "(데이터 없음)"
        processing = repo.list_processing_messages_by_user(str(chat_id))
        queued = repo.list_queued_messages_by_user(str(chat_id))
        lines = []
        if processing:
            lines.append(f"진행 중인 작업: {len(processing)}개")
            for msg in processing:
                lines.append(f"  - {msg.get('request', '')[:50]}")
        else:
            lines.append("진행 중인 작업 없음")
        if queued:
            lines.append(f"대기 중인 메시지: {len(queued)}개")
        else:
            lines.append("대기 중인 메시지 없음")
        return "\n".join(lines)

    async def _ctx_todo(self, chat_id: int) -> str:
        repo = self._repository
        if not repo:
            return "(데이터 없음)"
        today_str = app_now().strftime("%Y-%m-%d")
        todos = repo.list_todos_by_date(chat_id, today_str)
        if not todos:
            return f"오늘({today_str}) 등록된 할일이 없습니다."
        lines = [f"오늘({today_str}) 할일 목록:"]
        for t in todos:
            status = "✅" if t.done else "⬜"
            lines.append(f"  {status} {t.text}")
        stats = repo.get_todo_stats(chat_id, today_str)
        if stats:
            lines.append(f"\n통계: 전체 {stats.get('total', 0)}개, 완료 {stats.get('done', 0)}개, 미완료 {stats.get('pending', 0)}개")
        return "\n".join(lines)

    async def _ctx_memo(self, chat_id: int) -> str:
        repo = self._repository
        if not repo:
            return "(데이터 없음)"
        memos = repo.list_memos(chat_id)
        if not memos:
            return "저장된 메모가 없습니다."
        lines = [f"저장된 메모 {len(memos)}개:"]
        for m in memos:
            content = m.content[:80]
            lines.append(f"  - #{m.id}: {content}")
        return "\n".join(lines)

    async def _ctx_weather(self, chat_id: int) -> str:
        repo = self._repository
        if not repo:
            return "(데이터 없음)"
        location = repo.get_weather_location(chat_id)
        if location:
            return f"마지막 조회 지역: {location.name}"
        return "최근 조회한 날씨 지역이 없습니다. 날씨 관련 질문을 자유롭게 해주세요."

    async def _ctx_diary(self, chat_id: int) -> str:
        if not self.plugins:
            return "(일기 플러그인 없음)"
        diary_plugin = self.plugins.get_plugin_by_name("diary")
        if not diary_plugin:
            return "(일기 플러그인 없음)"
        store = getattr(diary_plugin, 'storage', None)
        if not store:
            return "(데이터 없음)"
        today = app_now()
        try:
            entries = store.list_by_month(chat_id, today.year, today.month)
        except Exception as e:
            logger.warning(f"Diary context error: {e}")
            return "(일기 데이터 조회 실패)"
        if not entries:
            return f"{today.year}년 {today.month}월에 작성된 일기가 없습니다."
        lines = [f"{today.year}년 {today.month}월 일기 ({len(entries)}개):"]
        for d in entries:
            content = d.content[:60]
            lines.append(f"  - {d.date}: {content}...")
        return "\n".join(lines)
