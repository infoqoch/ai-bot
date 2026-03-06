"""Message Queue Worker - 순차 메시지 처리."""

import asyncio
from typing import Optional, TYPE_CHECKING

from telegram import Bot

from src.logging_config import logger
from src.repository import Repository

if TYPE_CHECKING:
    from src.claude.client import ClaudeClient
    from src.services.session_service import SessionService


class QueueWorker:
    """큐 워커 - chat_id별 메시지를 순차 처리."""

    def __init__(
        self,
        repository: Repository,
        claude_client: "ClaudeClient",
        session_service: "SessionService",
        bot: Bot,
    ):
        self._repo = repository
        self._claude = claude_client
        self._session_service = session_service
        self._bot = bot
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_chats: set[int] = set()  # 현재 처리 중인 chat_id

    def start(self) -> None:
        """워커 시작."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("QueueWorker started")

    def stop(self) -> None:
        """워커 중지."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("QueueWorker stopped")

    async def notify_new_message(self, chat_id: int) -> None:
        """새 메시지 알림 - 해당 채팅의 처리 시작."""
        if chat_id not in self._active_chats:
            asyncio.create_task(self._process_chat_queue(chat_id))

    async def _worker_loop(self) -> None:
        """메인 워커 루프 - stale 메시지 복구 및 정리."""
        while self._running:
            try:
                # 30분 이상 처리 중인 메시지 복구
                reset_count = self._repo.reset_stale_processing_messages(30)
                if reset_count > 0:
                    logger.warning(f"Reset {reset_count} stale processing messages")

                # 7일 지난 완료 메시지 정리
                cleanup_count = self._repo.cleanup_old_completed_messages(7)
                if cleanup_count > 0:
                    logger.info(f"Cleaned up {cleanup_count} old completed messages")

                await asyncio.sleep(60)  # 1분마다 체크
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"QueueWorker loop error: {e}")
                await asyncio.sleep(10)

    async def _process_chat_queue(self, chat_id: int) -> None:
        """특정 채팅의 큐 처리."""
        if chat_id in self._active_chats:
            return

        self._active_chats.add(chat_id)
        logger.debug(f"[Queue] Start processing chat={chat_id}")

        try:
            while True:
                # 다음 대기 메시지 가져오기
                msg = self._repo.get_next_pending_message(chat_id)
                if not msg:
                    break

                queue_id = msg["id"]

                # 메시지 클레임 (처리 중으로 변경)
                if not self._repo.claim_message(queue_id):
                    continue  # 다른 워커가 이미 클레임

                logger.info(f"[Queue] Processing id={queue_id}, chat={chat_id}, session={msg['session_id'][:8]}")

                try:
                    # Claude 호출
                    response = await self._claude.chat(
                        message=msg["request"],
                        session_id=msg["session_id"],
                        model=msg["model"],
                        workspace_path=msg.get("workspace_path"),
                    )

                    if response.error:
                        # 에러 응답
                        error_text = f"❌ 오류 발생: {response.error.value}"
                        self._repo.complete_message(queue_id, error=response.error.value)
                        await self._send_response(chat_id, error_text, msg["session_id"])
                    else:
                        # 정상 응답
                        self._repo.complete_message(queue_id, response=response.text)
                        if response.text:
                            await self._send_response(chat_id, response.text, msg["session_id"])
                        else:
                            await self._send_response(chat_id, "(응답 없음)", msg["session_id"])

                    # 히스토리에 기록
                    self._repo.add_message(
                        msg["session_id"],
                        msg["request"],
                        processed=True,
                        processor="claude"
                    )

                except Exception as e:
                    logger.exception(f"[Queue] Error processing id={queue_id}: {e}")
                    self._repo.complete_message(queue_id, error=str(e))
                    await self._send_response(chat_id, f"❌ 처리 오류: {str(e)[:100]}", msg["session_id"])

        finally:
            self._active_chats.discard(chat_id)
            logger.debug(f"[Queue] Finished processing chat={chat_id}")

    async def _send_response(self, chat_id: int, text: str, session_id: str) -> None:
        """텔레그램에 응답 전송."""
        try:
            # 메시지 길이 제한 (텔레그램 최대 4096자)
            if len(text) > 4000:
                text = text[:4000] + "\n\n... (truncated)"

            # 세션 suffix 추가
            suffix = f"\n\n/s_{session_id[:8]} switch\n/h_{session_id[:8]} history"
            text = text + suffix

            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"[Queue] Failed to send response to chat={chat_id}: {e}")

    def get_queue_status(self, chat_id: int) -> dict:
        """큐 상태 조회."""
        pending = self._repo.get_pending_message_count(chat_id)
        processing = self._repo.get_processing_message(chat_id)
        return {
            "pending_count": pending,
            "is_processing": processing is not None,
            "current_message": processing["request"][:50] if processing else None,
        }
