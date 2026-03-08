"""Bot supervisor - 크래시 시 자동 재시작.

부모-자식 프로세스 구조로 봇을 감시하고 비정상 종료 시 재시작.
크로스플랫폼 (macOS, Linux) 지원.
"""

import atexit
import html
import os
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from src.config import get_settings
from src.logging_config import logger, setup_logging
from src.lock import ProcessLock
from src.runtime_exit_codes import RuntimeExitCode, describe_exit_code, is_restartable_exit_code

# .env 파일 로드 (supervisor는 별도 프로세스라 직접 로드 필요)
load_dotenv()

# 상수
MAX_RESTART_DELAY = 300  # 최대 5분
INITIAL_RESTART_DELAY = 5  # 초기 5초
CRASH_RESET_TIME = 60  # 60초 이상 정상 실행 시 딜레이 리셋

# 전역 상태
_process_lock = ProcessLock(Path("/tmp/telegram-bot-supervisor.lock"))
_child_process = None
_shutdown_requested = False
_telegram_token = None
_admin_chat_id = None


def _get_int_env(name: str, default: int) -> int:
    """Return one integer env var with fallback logging."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default

    try:
        return int(raw)
    except ValueError:
        logger.warning(f"정수 환경변수 파싱 실패 - {name}={raw!r}, default={default}")
        return default


CRASH_LOOP_WINDOW_SECONDS = _get_int_env("SUPERVISOR_CRASH_LOOP_WINDOW_SECONDS", 300)
CRASH_LOOP_MAX_CRASHES = _get_int_env("SUPERVISOR_CRASH_LOOP_MAX_CRASHES", 5)


def _load_telegram_config():
    """환경변수에서 텔레그램 설정 로드."""
    global _telegram_token, _admin_chat_id
    _telegram_token = os.getenv("TELEGRAM_TOKEN")
    _admin_chat_id = os.getenv("ADMIN_CHAT_ID")
    if _admin_chat_id:
        try:
            _admin_chat_id = int(_admin_chat_id)
        except ValueError:
            _admin_chat_id = None


def _escape_html(text: str) -> str:
    """Escape one operator-facing string for Telegram HTML."""
    return html.escape(text or "")


def _notify_startup_failure(summary: str, detail: str = "") -> None:
    """Best-effort admin alert for startup failures before the bot is running."""
    escaped_summary = _escape_html(summary)
    message = f"❌ <b>봇 시작 실패</b>\n\n{escaped_summary}"
    if detail:
        escaped_detail = _escape_html(detail)
        message += f"\n\n<code>{escaped_detail[:700]}</code>"
    notify_admin(message)


def _run_preflight() -> bool:
    """Validate unrecoverable startup conditions before spawning main."""
    try:
        settings = get_settings()
    except Exception as exc:
        logger.error(f"Supervisor preflight failed: invalid settings: {exc}")
        _notify_startup_failure("설정 오류로 시작하지 못했습니다.", str(exc))
        return False

    if not settings.telegram_token:
        logger.error("Supervisor preflight failed: TELEGRAM_TOKEN is empty")
        _notify_startup_failure("TELEGRAM_TOKEN is 비어 있어 시작하지 못했습니다.")
        return False

    return True


def _record_crash_time(crash_times: deque[float], occurred_at: float, *, window_seconds: int = CRASH_LOOP_WINDOW_SECONDS) -> int:
    """Append one crash timestamp and return the number still inside the window."""
    crash_times.append(occurred_at)
    cutoff = occurred_at - max(window_seconds, 1)
    while crash_times and crash_times[0] < cutoff:
        crash_times.popleft()
    return len(crash_times)


def notify_admin(message: str) -> bool:
    """관리자에게 텔레그램 메시지 전송.

    Args:
        message: 전송할 메시지 (HTML 형식 지원)

    Returns:
        성공 여부
    """
    if not _telegram_token or not _admin_chat_id:
        logger.trace("관리자 알림 스킵 - 설정 없음")
        return False

    try:
        url = f"https://api.telegram.org/bot{_telegram_token}/sendMessage"
        data = {
            "chat_id": _admin_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }

        with httpx.Client(timeout=10) as client:
            response = client.post(url, json=data)

        if response.status_code == 200:
            logger.info(f"관리자 알림 전송 성공")
            return True
        else:
            logger.warning(f"관리자 알림 실패: {response.status_code}")
            return False

    except Exception as e:
        logger.warning(f"관리자 알림 오류: {e}")
        return False


def signal_handler(signum, frame):
    """시그널 핸들러 - 자식에게 전달 후 종료."""
    global _shutdown_requested, _child_process

    sig_name = signal.Signals(signum).name
    logger.info(f"시그널 수신: {sig_name}")
    logger.trace(f"signum={signum}, frame={frame}")
    _shutdown_requested = True

    if _child_process and _child_process.poll() is None:
        logger.info("자식 프로세스에 SIGTERM 전달...")
        logger.trace(f"child_pid={_child_process.pid}")
        _child_process.terminate()
        try:
            _child_process.wait(timeout=10)
            logger.trace("자식 프로세스 정상 종료됨")
        except subprocess.TimeoutExpired:
            logger.warning("자식 프로세스 강제 종료 (SIGKILL)")
            _child_process.kill()


def run_bot() -> int:
    """봇 프로세스 실행 및 종료 대기. exit code 반환."""
    global _child_process

    cmd = [sys.executable, "-u", "-m", "src.main"]
    cwd = Path(__file__).parent.parent

    logger.info(f"봇 시작: {' '.join(cmd)}")
    logger.trace(f"작업 디렉토리: {cwd}")
    logger.trace(f"Python: {sys.executable}")
    logger.trace(f"환경변수 LOG_LEVEL: {os.getenv('LOG_LEVEL', 'INFO')}")

    _child_process = subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=cwd,
    )

    child_pid = _child_process.pid
    logger.trace(f"자식 프로세스 생성됨 - PID: {child_pid}")

    logger.trace("자식 프로세스 종료 대기 중...")
    exit_code = _child_process.wait()
    _child_process = None

    logger.trace(f"자식 프로세스 종료 - PID={child_pid}, exit_code={exit_code}")
    return exit_code


def main():
    """Supervisor 메인 루프."""
    global _shutdown_requested

    # 로깅 초기화
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")
    setup_logging(level=log_level, log_file=log_file)

    logger.trace("main() 시작")

    # 텔레그램 설정 로드
    _load_telegram_config()

    # 싱글톤 락
    if not _process_lock.acquire():
        print("❌ Supervisor가 이미 실행 중입니다.", file=sys.stderr)
        sys.exit(1)

    atexit.register(_process_lock.release)
    logger.trace("종료 핸들러 등록됨")

    if not _run_preflight():
        _process_lock.release()
        sys.exit(int(RuntimeExitCode.CONFIG_ERROR))

    # 시그널 핸들러 등록
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    logger.trace("시그널 핸들러 등록됨")

    logger.info("=" * 60)
    logger.info("Telegram Bot Supervisor 시작")
    logger.info(f"  PID: {os.getpid()}")
    logger.info(f"  LOG_LEVEL: {log_level}")
    logger.info("=" * 60)

    # 시작 알림
    start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notify_admin(f"🟢 <b>봇이 시작되었습니다</b>\n\n<code>{start_time_str}</code>")

    restart_delay = INITIAL_RESTART_DELAY
    restart_count = 0
    crash_times: deque[float] = deque()
    shutdown_reason = "shutdown requested"

    global _shutdown_requested
    _shutdown_requested = False

    while not _shutdown_requested:
        start_time = time.time()
        logger.trace(f"메인 루프 반복 - restart_count={restart_count}, delay={restart_delay}")

        try:
            exit_code = run_bot()
        except Exception as e:
            logger.exception(f"봇 실행 오류: {e}")
            exit_code = 1

        run_duration = time.time() - start_time
        logger.trace(f"봇 종료 - exit_code={exit_code}, duration={run_duration:.1f}s")

        # 종료 요청 확인
        if _shutdown_requested:
            logger.info("정상 종료 요청으로 supervisor 종료")
            shutdown_reason = "shutdown requested"
            break

        # 정상 종료 (exit code 0)
        if exit_code == 0:
            logger.info("봇 정상 종료 (exit_code=0), supervisor 종료")
            shutdown_reason = "main exited normally"
            break

        if not is_restartable_exit_code(exit_code):
            shutdown_reason = f"main exited unrecoverably ({describe_exit_code(exit_code)})"
            logger.error(f"봇 재시작 중단 - {shutdown_reason}")
            break

        # 비정상 종료 - 재시작
        restart_count += 1
        logger.warning(
            f"봇 비정상 종료 (exit_code={exit_code}, "
            f"실행시간={run_duration:.1f}초, 재시작횟수={restart_count})"
        )

        recent_crashes = _record_crash_time(crash_times, time.time())
        if CRASH_LOOP_MAX_CRASHES > 0 and recent_crashes >= CRASH_LOOP_MAX_CRASHES:
            shutdown_reason = (
                f"crash loop detected ({recent_crashes} crashes within "
                f"{CRASH_LOOP_WINDOW_SECONDS} seconds, last={describe_exit_code(exit_code)})"
            )
            logger.error(f"봇 재시작 중단 - {shutdown_reason}")
            break

        # 충분히 오래 실행됐으면 딜레이 리셋
        if run_duration >= CRASH_RESET_TIME:
            restart_delay = INITIAL_RESTART_DELAY
            logger.info("안정 실행 확인, 재시작 딜레이 리셋")
            logger.trace(f"run_duration({run_duration:.1f}) >= CRASH_RESET_TIME({CRASH_RESET_TIME})")

        logger.info(f"{restart_delay}초 후 재시작...")

        # 대기 (중간에 종료 요청 체크)
        logger.trace("재시작 대기 시작")
        for i in range(restart_delay):
            if _shutdown_requested:
                logger.trace("대기 중 종료 요청 감지")
                break
            time.sleep(1)

        # 지수 백오프 (최대 5분)
        old_delay = restart_delay
        restart_delay = min(restart_delay * 2, MAX_RESTART_DELAY)
        logger.trace(f"지수 백오프: {old_delay} -> {restart_delay}")

    # 종료 알림
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notify_admin(
        "🔴 <b>봇이 종료되었습니다</b>\n\n"
        f"<code>{end_time}</code>\n"
        f"<b>Reason:</b> {_escape_html(shutdown_reason)}"
    )

    logger.info("=" * 60)
    logger.info("Supervisor 종료")
    logger.info(f"  총 재시작 횟수: {restart_count}")
    logger.info(f"  종료 사유: {shutdown_reason}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
