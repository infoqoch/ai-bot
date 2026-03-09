"""Async Claude Code CLI client."""

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import json
import os
import pty
import re
import select
import shlex
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_USAGE_RE = re.compile(
    r"5h:\s*(?P<five_hour_percent>\d+)%\s*\((?P<five_hour_reset>[^)]+)\).*?"
    r"wk:\s*(?P<weekly_percent>\d+)%\s*\((?P<weekly_reset>[^)]+)\)",
    re.IGNORECASE | re.DOTALL,
)

from src.ai.catalog import get_profile
from src.ai.client_types import ChatError, ChatResponse
from src.logging_config import logger


class ClaudeClient:
    """Async wrapper for Claude Code CLI."""

    def __init__(
        self,
        command: str = "claude",
        system_prompt_file: Optional[Path] = None,
        timeout: Optional[int] = None,
    ):
        logger.trace(f"ClaudeClient.__init__() - command='{command}', timeout={timeout}")
        self.command_parts = shlex.split(command)
        self.system_prompt = self._load_system_prompt(system_prompt_file)
        self.timeout = timeout
        logger.trace(f"command_parts={self.command_parts}")
        logger.trace(f"system_prompt loaded={self.system_prompt is not None}")

    def _load_system_prompt(self, path: Optional[Path]) -> Optional[str]:
        logger.trace(f"_load_system_prompt() - path={path}")
        if path and path.exists():
            content = path.read_text(encoding="utf-8")
            logger.trace(f"시스템 프롬프트 로드됨 - length={len(content)}")
            return content
        logger.trace("시스템 프롬프트 없음")
        return None

    async def _run_command(
        self,
        cmd: list[str],
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """Execute command and return (stdout, stderr, returncode).

        Args:
            cmd: Command to execute
            timeout: Optional timeout in seconds. If None, wait indefinitely.
            cwd: Working directory for the command. If None, use current directory.
        """
        cmd_preview = " ".join(cmd[:5]) + f" ... ({len(cmd)} parts)"
        logger.trace(f"_run_command() - cmd={cmd_preview}")
        logger.trace(f"timeout={timeout}초" if timeout else "timeout=None (무제한)")
        logger.trace(f"cwd={cwd or '(현재 디렉토리)'}")

        logger.trace("subprocess 생성 중")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        logger.trace(f"subprocess 생성됨 - pid={process.pid}")

        logger.trace("프로세스 실행 대기 중")
        try:
            if timeout:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            else:
                # 타임아웃 없이 무제한 대기
                stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            with suppress(ProcessLookupError):
                process.kill()
            with suppress(Exception):
                await process.communicate()
            raise
        except asyncio.TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            with suppress(Exception):
                await process.communicate()
            raise
        stdout_str = stdout.decode("utf-8").strip()
        stderr_str = stderr.decode("utf-8").strip()

        logger.trace(f"프로세스 완료 - returncode={process.returncode}")
        logger.trace(f"stdout length={len(stdout_str)}")
        logger.trace(f"stderr length={len(stderr_str)}")

        if stderr_str:
            logger.trace(f"stderr 내용: {stderr_str[:200]}")

        return (stdout_str, stderr_str, process.returncode)

    async def create_session(self, workspace_path: Optional[str] = None) -> Optional[str]:
        """Create a new Claude session and return session_id.

        Args:
            workspace_path: Workspace directory path (for workspace sessions)
        """
        logger.trace(f"create_session() 시작 - workspace_path={workspace_path or '(없음)'}")
        logger.info("새 Claude 세션 생성 중")

        response = await self.chat("answer 'hi'", None, workspace_path=workspace_path)

        if response.error:
            logger.error(f"세션 생성 실패: {response.error.value}")
            return None

        logger.info(f"새 세션 생성됨: {response.session_id}")
        logger.trace(f"응답: {response.text[:100] if response.text else '(없음)'}")
        return response.session_id

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> ChatResponse:
        """
        Send a message to Claude.

        Args:
            message: User message
            session_id: Claude's session ID (always use --resume if provided)
            model: Model to use (opus, sonnet, haiku)
            workspace_path: Workspace directory path (for workspace sessions)

        Returns:
            ChatResponse with text, error, and session_id
        """
        short_msg = message[:50] + "..." if len(message) > 50 else message
        logger.trace(f"chat() 시작 - msg='{short_msg}'")
        logger.trace(f"session_id={session_id[:8] if session_id else 'None'}, model={model}, workspace={workspace_path or '(없음)'}")

        normalized_model = get_profile("claude", model).key if model else None
        cmd = self._build_command(message, session_id, normalized_model, workspace_path)
        logger.trace(f"명령어 생성됨 - {len(cmd)} parts")

        try:
            logger.trace("CLI 실행 시작")
            output, error, returncode = await self._run_command(cmd, timeout=self.timeout, cwd=workspace_path)

            logger.trace(f"CLI 결과 - returncode={returncode}")

            if returncode != 0:
                # 에러 상세 로깅 - stdout, stderr 둘 다 출력
                logger.error(f"Claude CLI 비정상 종료 - returncode={returncode}")
                logger.error(f"  stderr: {error if error else '(비어있음)'}")
                logger.error(f"  stdout: {output[:500] if output else '(비어있음)'}")
                logger.error(f"  session_id: {session_id[:8] if session_id else 'None'}")
                logger.error(f"  message: {short_msg}")

                # 실행한 명령어 (메시지 내용 제외)
                cmd_preview = " ".join(cmd[:-1])  # 마지막 인자(메시지) 제외
                logger.debug(f"  command: {cmd_preview} <message>")

                if error and ("not found" in error.lower() or "no conversation found" in error.lower() or "invalid" in error.lower()):
                    logger.warning(f"세션을 찾을 수 없음: {error[:100]}")
                    return ChatResponse("", ChatError.SESSION_NOT_FOUND, None)

                # 에러 메시지 결합 (둘 다 있으면 합침)
                error_detail = error or output or "(오류 내용 없음)"
                return ChatResponse(error_detail, ChatError.CLI_ERROR, None)

            # JSON 파싱
            logger.trace("JSON 파싱 시도")
            logger.debug(f"[RAW OUTPUT] length={len(output)}, preview={repr(output[:300]) if output else 'EMPTY'}")
            try:
                data = json.loads(output)
                result = data.get("result", "")
                new_session_id = data.get("session_id")

                logger.trace(f"파싱 성공 - session_id={new_session_id}")
                logger.debug(f"[PARSED] result type={type(result)}, length={len(result) if result else 0}")
                logger.debug(f"[PARSED] result preview={repr(result[:200]) if result else 'EMPTY/NONE'}")
                logger.debug(f"[PARSED] all keys={list(data.keys())}")

                # 빈 result 감지 - 원인 추적
                if not result or not result.strip():
                    logger.warning(f"[EMPTY RESULT] Claude returned empty result!")
                    logger.warning(f"  raw data keys: {list(data.keys())}")
                    logger.warning(f"  raw data: {json.dumps(data, ensure_ascii=False)[:500]}")

                logger.info(f"Claude 응답 - session_id={new_session_id}")

                return ChatResponse(result, None, new_session_id)

            except json.JSONDecodeError as e:
                # JSON 파싱 실패 시 원본 반환
                logger.warning(f"JSON 파싱 실패: {e}")
                logger.warning(f"[JSON ERROR] 원본 output: {repr(output[:500]) if output else 'EMPTY'}")
                return ChatResponse(output or "(응답 없음)", None, None)

        except asyncio.TimeoutError:
            logger.warning(
                f"Claude CLI timed out - session={session_id[:8] if session_id else 'None'}, "
                f"timeout={self.timeout}"
            )
            return ChatResponse("", ChatError.TIMEOUT, session_id)
        except Exception as e:
            logger.exception(f"Claude CLI 오류: {e}")
            return ChatResponse("", ChatError.CLI_ERROR, None)

    async def get_usage_snapshot(self) -> Optional[dict[str, str]]:
        """Return the current Claude Code subscription usage snapshot."""
        auth_snapshot = await self._get_auth_snapshot()
        if not auth_snapshot:
            return None

        snapshot = {
            "subscription_type": auth_snapshot["subscription_type"],
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        omc_snapshot = await self._get_usage_snapshot_from_omc()
        if omc_snapshot:
            snapshot.update(omc_snapshot)
            return snapshot

        raw_screen = await asyncio.to_thread(self._capture_usage_screen)
        if raw_screen:
            cleaned = self._strip_ansi(raw_screen)
            match = _USAGE_RE.search(cleaned)
            if match:
                snapshot.update({key: value.strip() for key, value in match.groupdict().items()})
                return snapshot
            logger.warning(f"Claude usage screen parse failed: {cleaned[:300]!r}")
        else:
            logger.warning("Claude usage screen capture returned empty output")

        unavailable_reason = await self._get_usage_unavailable_reason()
        snapshot["unavailable_reason"] = unavailable_reason or "Usage endpoint temporarily unavailable"
        return snapshot

    async def _get_auth_snapshot(self) -> Optional[dict[str, str]]:
        """Read Claude auth status and return plan details."""
        auth_stdout, auth_stderr, auth_returncode = await self._run_command(
            [*self.command_parts, "auth", "status"],
            timeout=10,
        )
        if auth_returncode != 0:
            logger.warning(f"Claude auth status failed: {auth_stderr or auth_stdout}")
            return None

        subscription_type = "unknown"
        try:
            auth_data = json.loads(auth_stdout)
            if not auth_data.get("loggedIn"):
                logger.warning("Claude auth status reports loggedOut state")
                return None
            subscription_type = str(auth_data.get("subscriptionType") or "unknown")
        except json.JSONDecodeError:
            logger.debug("Claude auth status was not JSON; continuing without subscription_type")

        return {"subscription_type": subscription_type}

    async def _get_usage_snapshot_from_omc(self) -> Optional[dict[str, str]]:
        """Best-effort usage lookup via oh-my-claudecode's usage API."""
        usage_api_path = self._find_omc_usage_api_path()
        if not usage_api_path:
            logger.debug("OMC usage-api.js not found; skipping plugin usage lookup")
            return None

        script = """
import { pathToFileURL } from "node:url";

const usageApiPath = process.argv[1];

try {
  const mod = await import(pathToFileURL(usageApiPath).href);
  const data = await mod.getUsage();
  process.stdout.write(JSON.stringify({ data }));
} catch (error) {
  process.stdout.write(JSON.stringify({ error: String(error) }));
}
"""
        try:
            stdout, stderr, returncode = await self._run_command(
                ["node", "--input-type=module", "-e", script, str(usage_api_path)],
                timeout=15,
            )
        except Exception as exc:
            logger.debug(f"OMC usage lookup failed to execute: {exc}")
            return None

        if returncode != 0:
            logger.warning(f"OMC usage lookup failed: {stderr or stdout}")
            return None

        try:
            payload = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            logger.warning(f"OMC usage lookup returned non-JSON: {stdout[:200]!r}")
            return None

        if payload.get("error"):
            logger.warning(f"OMC usage lookup errored: {payload['error']}")
            return None

        data = payload.get("data")
        if not isinstance(data, dict):
            return None

        five_hour_percent = self._format_usage_percent(data.get("fiveHourPercent"))
        weekly_percent = self._format_usage_percent(data.get("weeklyPercent"))
        if five_hour_percent is None or weekly_percent is None:
            return None

        return {
            "five_hour_percent": five_hour_percent,
            "five_hour_reset": self._format_reset_window(data.get("fiveHourResetsAt")),
            "weekly_percent": weekly_percent,
            "weekly_reset": self._format_reset_window(data.get("weeklyResetsAt")),
        }

    async def _get_usage_unavailable_reason(self) -> Optional[str]:
        """Best-effort detail for why usage data is currently unavailable."""
        script = """
import { execSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import https from "node:https";
import { homedir } from "node:os";
import { join } from "node:path";

function readKeychainCredentials() {
  if (process.platform !== "darwin") return null;
  try {
    const raw = execSync('/usr/bin/security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null', {
      encoding: "utf8",
      timeout: 2000,
    }).trim();
    const parsed = JSON.parse(raw);
    const creds = parsed.claudeAiOauth || parsed;
    return creds.accessToken ? creds : null;
  } catch {
    return null;
  }
}

function readFileCredentials() {
  try {
    const credPath = join(homedir(), ".claude/.credentials.json");
    if (!existsSync(credPath)) return null;
    const parsed = JSON.parse(readFileSync(credPath, "utf8"));
    const creds = parsed.claudeAiOauth || parsed;
    return creds.accessToken ? creds : null;
  } catch {
    return null;
  }
}

const creds = readKeychainCredentials() || readFileCredentials();
if (!creds?.accessToken) {
  process.stdout.write(JSON.stringify({ reason: "Claude credentials unavailable" }));
  process.exit(0);
}

const req = https.request({
  hostname: "api.anthropic.com",
  path: "/api/oauth/usage",
  method: "GET",
  headers: {
    Authorization: `Bearer ${creds.accessToken}`,
    "anthropic-beta": "oauth-2025-04-20",
    "Content-Type": "application/json",
  },
  timeout: 10000,
}, (res) => {
  let data = "";
  res.on("data", (chunk) => { data += chunk; });
  res.on("end", () => {
    if (res.statusCode === 200) {
      process.stdout.write(JSON.stringify({ reason: null }));
      return;
    }

    let parsed = null;
    try {
      parsed = JSON.parse(data);
    } catch {}

    const error = parsed?.error || {};
    process.stdout.write(JSON.stringify({
      reason: error.message || `HTTP ${res.statusCode}`,
      statusCode: res.statusCode,
      errorType: error.type || null,
    }));
  });
});

req.on("error", (error) => {
  process.stdout.write(JSON.stringify({ reason: String(error) }));
});

req.on("timeout", () => {
  req.destroy(new Error("timeout"));
});

req.end();
"""
        try:
            stdout, stderr, returncode = await self._run_command(
                ["node", "--input-type=module", "-e", script],
                timeout=15,
            )
        except Exception as exc:
            logger.debug(f"Usage unavailable-reason lookup failed to execute: {exc}")
            return None

        if returncode != 0:
            logger.warning(f"Usage unavailable-reason lookup failed: {stderr or stdout}")
            return None

        try:
            payload = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            logger.warning(f"Usage unavailable-reason lookup returned non-JSON: {stdout[:200]!r}")
            return None

        reason = payload.get("reason")
        if not reason:
            return None

        status_code = payload.get("statusCode")
        error_type = payload.get("errorType")
        suffix_parts = [str(part) for part in (status_code, error_type) if part]
        if suffix_parts:
            return f"{reason} ({', '.join(suffix_parts)})"
        return str(reason)

    @staticmethod
    def _find_omc_usage_api_path() -> Optional[Path]:
        """Return the newest installed oh-my-claudecode usage API path."""
        cache_root = Path.home() / ".claude" / "plugins" / "cache" / "omc" / "oh-my-claudecode"
        if not cache_root.exists():
            return None

        candidates = list(cache_root.glob("*/dist/hud/usage-api.js"))
        if not candidates:
            return None

        return max(candidates, key=lambda path: path.stat().st_mtime)

    @staticmethod
    def _format_usage_percent(value) -> Optional[str]:
        """Normalize one percentage value to a whole-number string."""
        try:
            return str(int(round(float(value))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_reset_window(value) -> str:
        """Format an ISO reset timestamp as a compact relative window."""
        if not value:
            return "unknown"

        try:
            reset_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)

        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=timezone.utc)

        remaining = int((reset_at - datetime.now(timezone.utc)).total_seconds())
        if remaining <= 0:
            return "soon"

        days, rem = divmod(remaining, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)

        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes or not parts:
            parts.append(f"{minutes}m")
        return "".join(parts)

    def _capture_usage_screen(self, startup_timeout: float = 3.0) -> str:
        """Launch Claude in a PTY briefly and capture the startup status line."""
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            self.command_parts,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)

        chunks: list[bytes] = []
        deadline = time.monotonic() + startup_timeout
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master_fd], [], [], 0.25)
                if not ready:
                    continue

                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break

                if not chunk:
                    break

                chunks.append(chunk)
                if b"5h:" in chunk and b"wk:" in chunk:
                    # Collect one extra frame so reset strings are included before shutdown.
                    settle_deadline = time.monotonic() + 0.35
                    while time.monotonic() < settle_deadline:
                        ready, _, _ = select.select([master_fd], [], [], 0.05)
                        if not ready:
                            continue
                        try:
                            extra = os.read(master_fd, 4096)
                        except OSError:
                            extra = b""
                        if not extra:
                            break
                        chunks.append(extra)
                    break
        finally:
            for sig in (signal.SIGINT, signal.SIGINT, signal.SIGTERM):
                if process.poll() is not None:
                    break
                with suppress(Exception):
                    process.send_signal(sig)
                time.sleep(0.05)

            if process.poll() is None:
                with suppress(Exception):
                    process.kill()
            with suppress(Exception):
                process.wait(timeout=1)
            with suppress(OSError):
                os.close(master_fd)

        return b"".join(chunks).decode("utf-8", errors="ignore")

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Remove ANSI control codes from terminal output."""
        return _ANSI_RE.sub("", text).replace("\r", "")

    def _build_command(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> list[str]:
        """Build Claude CLI command."""
        logger.trace(f"_build_command() - session={session_id[:8] if session_id else 'None'}, model={model}, workspace={workspace_path or '(없음)'}")

        cmd = list(self.command_parts)

        # 모델 지정
        if model:
            cmd.extend(["--model", model])
            logger.trace(f"--model {model} 옵션 추가됨")

        # 세션이 있으면 resume 사용 (유효한 UUID만)
        if session_id and _UUID_RE.match(session_id):
            cmd.extend(["--resume", session_id])
            logger.trace("--resume 옵션 추가됨")
        elif session_id:
            logger.warning(f"Invalid UUID for --resume, starting new session: {session_id[:16]}")

        # JSON 출력 (session_id 파싱용)
        cmd.extend(["--print", "--output-format", "json"])
        logger.trace("JSON 출력 옵션 추가됨")

        # 도구 권한 자동 승인 (WebSearch 등 스케줄러에서 필요)
        cmd.append("--dangerously-skip-permissions")
        logger.trace("--dangerously-skip-permissions 옵션 추가됨")

        if self.system_prompt:
            cmd.extend(["--system-prompt", self.system_prompt])
            logger.trace("시스템 프롬프트 옵션 추가됨")

        # 워크스페이스 세션: 텔레그램 응답 포맷 추가 (워크스페이스 CLAUDE.md + 텔레그램 포맷)
        if workspace_path:
            telegram_format_prompt = (
                "응답 포맷 규칙: "
                "1) Telegram HTML 사용 (<b>, <i>, <code>, <pre>) "
                "2) 마크다운 금지 (**, *, #, ```) "
                "3) 모바일 최적화 (간결하게) "
                "4) 한국어로 응답"
            )
            cmd.extend(["--append-system-prompt", telegram_format_prompt])
            logger.trace("워크스페이스 세션 - 텔레그램 포맷 프롬프트 추가됨")

        cmd.append(message)
        logger.trace(f"최종 명령어 길이: {len(cmd)} parts")

        return cmd

    async def summarize(self, questions: list[str], max_questions: int = 10) -> str:
        """Generate a summary of conversation questions."""
        logger.trace(f"summarize() - questions={len(questions)}, max={max_questions}")

        if not questions:
            logger.trace("질문 없음")
            return "(내용 없음)"

        history_text = "\n".join(f"- {q[:100]}" for q in questions[:max_questions])
        logger.trace(f"히스토리 텍스트 생성됨 - length={len(history_text)}")

        prompt = f"""다음 질문들을 보고 이 대화 세션을 2-3문장으로 요약해주세요.
- 무엇을 하려고 했는지
- 주요 주제나 작업 내용
질문 없이 요약만 답변하세요.

질문들:
{history_text}"""

        cmd = list(self.command_parts) + [
            "--print",
            "--output-format", "text",
            "-p", prompt,
        ]

        logger.trace("요약 명령어 실행")

        try:
            output, _, _ = await self._run_command(cmd, timeout=60)
            result = output[:300] if output else "(요약 실패)"
            logger.trace(f"요약 완료 - length={len(result)}")
            return result

        except Exception as e:
            logger.warning(f"요약 실패: {e}")
            first_q = questions[0][:50]
            return f'"{first_q}..."'

    async def compact(self, session_id: str) -> ChatResponse:
        """Compact a Claude session to reduce context size.

        Args:
            session_id: Claude's session ID to compact

        Returns:
            ChatResponse with compact result
        """
        logger.trace(f"compact() - session_id={session_id[:8]}")
        logger.info(f"세션 compact 시작: {session_id[:8]}")

        # Claude CLI compact 명령어: claude --resume <session_id> /compact
        cmd = list(self.command_parts) + [
            "--resume", session_id,
            "--print",
            "--output-format", "json",
            "/compact",
        ]

        try:
            output, error, returncode = await self._run_command(cmd, timeout=120)

            if returncode != 0:
                logger.error(f"Compact 실패 - returncode={returncode}, error={error}")
                return ChatResponse(error or "(compact 실패)", ChatError.CLI_ERROR, session_id)

            # JSON 파싱 시도
            try:
                data = json.loads(output)
                result = data.get("result", "(응답 없음)")
                logger.info(f"Compact 완료: {session_id[:8]}")
                return ChatResponse(result, None, session_id)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 원본 반환
                logger.info(f"Compact 완료 (raw): {session_id[:8]}")
                return ChatResponse(output or "(compact 완료)", None, session_id)

        except asyncio.TimeoutError:
            logger.error(f"Compact 타임아웃: {session_id[:8]}")
            return ChatResponse("", ChatError.TIMEOUT, session_id)
        except Exception as e:
            logger.exception(f"Compact 오류: {e}")
            return ChatResponse(str(e), ChatError.CLI_ERROR, session_id)
