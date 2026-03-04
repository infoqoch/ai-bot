"""세션 스케줄러 - 매니저 세션 자동 compact."""

from datetime import time
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from src.logging_config import logger

if TYPE_CHECKING:
    from telegram.ext import Application
    from src.claude.session import SessionStore
    from src.claude.client import ClaudeClient


# 한국 시간대
KST = ZoneInfo("Asia/Seoul")

# Compact 스케줄 시간 (21:00 KST)
COMPACT_TIME = time(21, 0)


class SessionScheduler:
    """세션 관리 스케줄러."""

    def __init__(
        self,
        session_store: "SessionStore",
        claude_client: "ClaudeClient",
        admin_chat_id: Optional[int] = None,
    ):
        """
        Args:
            session_store: 세션 저장소
            claude_client: Claude CLI 클라이언트
            admin_chat_id: 보고 받을 채팅 ID (None이면 보고 안함)
        """
        self.sessions = session_store
        self.claude = claude_client
        self.admin_chat_id = admin_chat_id
        self._app: Optional["Application"] = None
        self._jobs = []

    def setup_jobs(self, app: "Application") -> None:
        """스케줄 작업 설정."""
        self._app = app
        job_queue = app.job_queue

        if job_queue is None:
            logger.error("job_queue가 없습니다. APScheduler가 설치되어 있는지 확인하세요.")
            return

        # 기존 작업 제거
        for job in self._jobs:
            job.schedule_removal()
        self._jobs.clear()

        # 21:00 - 매니저 세션 compact
        job = job_queue.run_daily(
            self._compact_manager_sessions,
            time=COMPACT_TIME,
            name="compact_manager_sessions",
        )
        self._jobs.append(job)
        logger.info("스케줄 등록: 21:00 매니저 세션 compact")

    async def _compact_manager_sessions(self, context) -> None:
        """21:00 - 모든 매니저 세션 compact."""
        logger.info("🗜️ 매니저 세션 compact 시작")

        results = []

        # 모든 사용자의 매니저 세션 찾기
        for user_id in self.sessions._data.keys():
            manager_session_id = self.sessions.get_manager_session_id(user_id)
            if not manager_session_id:
                continue

            try:
                # Claude compact 실행
                result = await self._run_compact(manager_session_id)
                results.append({
                    "user_id": user_id,
                    "session_id": manager_session_id[:8],
                    "success": result["success"],
                    "message": result["message"],
                })
                logger.info(f"Compact 완료: user={user_id}, session={manager_session_id[:8]}")
            except Exception as e:
                results.append({
                    "user_id": user_id,
                    "session_id": manager_session_id[:8],
                    "success": False,
                    "message": str(e),
                })
                logger.error(f"Compact 실패: user={user_id}, error={e}")

        # 관리자에게 보고
        if self.admin_chat_id and results:
            await self._send_report(context, results)

    async def _run_compact(self, session_id: str) -> dict:
        """Claude CLI로 compact 실행."""
        try:
            response = await self.claude.compact(session_id)
            return {
                "success": response.error is None,
                "message": response.text[:200] if response.text else "(응답 없음)",
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }

    async def _send_report(self, context, results: list[dict]) -> None:
        """관리자에게 compact 결과 보고."""
        if not self.admin_chat_id:
            return

        success_count = sum(1 for r in results if r["success"])
        fail_count = len(results) - success_count

        lines = [
            "🗜️ <b>매니저 세션 Compact 보고</b>",
            "",
            f"✅ 성공: {success_count}개",
            f"❌ 실패: {fail_count}개",
            "",
        ]

        for r in results:
            status = "✅" if r["success"] else "❌"
            lines.append(f"{status} <code>{r['session_id']}</code>: {r['message'][:50]}")

        try:
            await context.bot.send_message(
                chat_id=self.admin_chat_id,
                text="\n".join(lines),
                parse_mode="HTML",
            )
            logger.info(f"Compact 보고 전송 완료: chat_id={self.admin_chat_id}")
        except Exception as e:
            logger.error(f"Compact 보고 전송 실패: {e}")

    async def compact_now(self, user_id: str) -> dict:
        """즉시 compact 실행 (수동 트리거용)."""
        manager_session_id = self.sessions.get_manager_session_id(user_id)
        if not manager_session_id:
            return {"success": False, "message": "매니저 세션 없음"}

        return await self._run_compact(manager_session_id)
