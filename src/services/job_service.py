"""Detached Claude job execution service."""

import asyncio
import os
import time
from typing import Optional

from telegram import Bot

from src.bot.constants import LONG_TASK_THRESHOLD_SECONDS
from src.bot.formatters import truncate_message
from src.claude.client import ClaudeClient
from src.logging_config import clear_context, logger, set_session_id, set_trace_id, set_user_id
from src.repository import Repository
from src.services.session_service import SessionService


class JobService:
    """Run detached Claude jobs and deliver responses directly to Telegram."""

    def __init__(
        self,
        repo: Repository,
        session_service: SessionService,
        claude_client: ClaudeClient,
        telegram_token: str,
    ):
        self._repo = repo
        self._sessions = session_service
        self._claude = claude_client
        self._telegram_token = telegram_token

    async def run_job(self, job_id: int) -> bool:
        """Run one detached job and drain the persistent queue for the same session."""
        job = self._repo.get_message_log(job_id)
        if not job or job["processed"] == 2:
            logger.warning(f"Detached job missing or already completed: id={job_id}")
            return False

        session_id = job["session_id"]
        worker_pid = os.getpid()

        if not self._attach_or_acquire_lock(session_id, job_id, worker_pid):
            logger.warning(f"Detached job lock attach failed: job={job_id}, session={session_id[:8]}")
            return False

        bot = Bot(token=self._telegram_token)

        try:
            current_job = job

            while current_job:
                if current_job["processed"] == 0 and not self._repo.claim_pending_message(current_job["id"]):
                    logger.warning(f"Detached job claim failed: id={current_job['id']}")
                    break

                await self._execute_job(bot, current_job)

                next_queued = self._repo.pop_next_queued_message(session_id)
                if not next_queued:
                    current_job = None
                    continue

                next_job_id = self._repo.enqueue_message(
                    chat_id=next_queued["chat_id"],
                    session_id=next_queued["session_id"],
                    request=next_queued["message"],
                    model=next_queued["model"],
                    workspace_path=next_queued.get("workspace_path"),
                )
                current_job = self._repo.get_message_log(next_job_id)
                logger.info(
                    f"Detached worker continuing queued job: previous={job_id}, next={next_job_id}, "
                    f"session={session_id[:8]}"
                )

            return True
        finally:
            self._repo.release_session_lock(session_id, job_id)
            clear_context()

    def _attach_or_acquire_lock(self, session_id: str, job_id: int, worker_pid: int) -> bool:
        """Attach this worker to a reserved lock, or acquire it directly as fallback."""
        if self._repo.attach_worker_to_session_lock(session_id, job_id, worker_pid):
            return True

        existing = self._repo.get_session_lock(session_id)
        if existing and existing["job_id"] == job_id and existing.get("worker_pid") == worker_pid:
            return True

        if existing:
            return False

        if not self._repo.reserve_session_lock(session_id, job_id):
            return False

        return self._repo.attach_worker_to_session_lock(session_id, job_id, worker_pid)

    async def _execute_job(self, bot: Bot, job: dict) -> None:
        """Execute one Claude job and send the final response to Telegram."""
        job_id = job["id"]
        chat_id = job["chat_id"]
        session_id = job["session_id"]
        message = job["request"]
        model = job["model"]
        workspace_path = job.get("workspace_path") or self._sessions.get_workspace_path(session_id)

        trace_id = set_trace_id()
        set_user_id(str(chat_id))
        set_session_id(session_id)

        start_time = time.time()
        short_message = truncate_message(message, 30)
        long_task_notified = False

        logger.info(
            f"Detached Claude job start - job_id={job_id}, session={session_id[:8]}, model={model}"
        )

        async def notify_long_task() -> None:
            nonlocal long_task_notified
            await asyncio.sleep(LONG_TASK_THRESHOLD_SECONDS)
            long_task_notified = True
            elapsed_min = LONG_TASK_THRESHOLD_SECONDS // 60
            await bot.send_message(
                chat_id=chat_id,
                text=f"<code>{short_message}</code>\nTask taking {elapsed_min}+ minutes. Will notify on completion!",
                parse_mode="HTML",
            )

        notify_task = asyncio.create_task(notify_long_task())

        try:
            try:
                response, error, _ = await self._claude.chat(
                    message,
                    session_id,
                    model=model,
                    workspace_path=workspace_path or None,
                )
            finally:
                notify_task.cancel()
                try:
                    await notify_task
                except asyncio.CancelledError:
                    pass

            elapsed = time.time() - start_time
            logger.info(
                f"Detached Claude job complete - job_id={job_id}, session={session_id[:8]}, "
                f"elapsed={elapsed:.1f}s, error={error or '-'}"
            )

            self._sessions.add_message(session_id, message, processor="claude")

            if error == "TIMEOUT":
                response = "⏱️ Response timed out. Please try again."
            elif error and error != "SESSION_NOT_FOUND":
                response = f"❌ Error: {error}"
            elif not response or not response.strip():
                response = f"⚠️ <code>{short_message}</code>\nResponse is empty. Please try again."

            session_info = self._sessions.get_session_info(session_id)
            history_count = self._sessions.get_history_count(session_id)
            question_preview = truncate_message(message, 30)
            session_short_id = session_id[:8]

            full_response = (
                f"<b>[{session_info}|#{history_count}]</b>\n"
                f"<code>{question_preview}</code>\n\n"
                f"{response}\n\n"
                f"/s_{session_short_id} switch\n"
                f"/h_{session_short_id} history"
            )

            if long_task_notified:
                elapsed_min = int(elapsed // 60)
                elapsed_sec = int(elapsed % 60)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"<code>{short_message}</code>\nTask complete! ({elapsed_min}m {elapsed_sec}s)",
                    parse_mode="HTML",
                )

            await self._send_message_to_chat(bot, chat_id, full_response)
            self._repo.complete_message(job_id, response=response)

        except Exception as e:
            logger.exception(f"Detached Claude job failed: job_id={job_id}, trace={trace_id}, error={e}")
            self._repo.complete_message(job_id, error=str(e))
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ An error occurred. Please try again later.",
                )
            except Exception:
                logger.exception(f"Detached Claude job error delivery failed: job_id={job_id}")

    @staticmethod
    def _split_message(text: str, max_length: int = 4000) -> list[str]:
        """Split long Telegram messages on newline boundaries when possible."""
        if len(text) <= max_length:
            return [text]

        chunks: list[str] = []
        remaining = text

        while len(remaining) > max_length:
            window = remaining[:max_length]
            split_pos = window.rfind("\n")
            if split_pos > 0:
                chunk = remaining[:split_pos]
                remaining = remaining[split_pos + 1:]
            else:
                chunk = window
                remaining = remaining[max_length:]
            if chunk:
                chunks.append(chunk)

        if remaining:
            chunks.append(remaining)

        return chunks

    async def _send_message_to_chat(self, bot: Bot, chat_id: int, text: str) -> None:
        """Send a split-safe Telegram message with HTML fallback."""
        for chunk in self._split_message(text):
            try:
                await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")
            except Exception:
                await bot.send_message(chat_id=chat_id, text=chunk)
