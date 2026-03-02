"""Async Claude Code CLI client."""

import asyncio
import logging
import shlex
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Async wrapper for Claude Code CLI."""
    
    def __init__(
        self,
        command: str = "claude",
        system_prompt_file: Optional[Path] = None,
        timeout: int = 300,
    ):
        self.command_parts = shlex.split(command)
        self.system_prompt = self._load_system_prompt(system_prompt_file)
        self.timeout = timeout
    
    def _load_system_prompt(self, path: Optional[Path]) -> Optional[str]:
        if path and path.exists():
            return path.read_text(encoding="utf-8")
        return None
    
    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        resume: bool = False,
    ) -> tuple[str, Optional[str]]:
        """
        Send a message to Claude.
        
        Args:
            message: User message
            session_id: Session ID to use/resume
            resume: Whether to resume existing session
            
        Returns:
            Tuple of (response_text, error_message)
        """
        cmd = self._build_command(message, session_id, resume)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
            
            output = stdout.decode("utf-8").strip()
            error = stderr.decode("utf-8").strip()
            
            if process.returncode != 0 and error:
                # Check for session not found error
                if "not found" in error.lower() or "invalid" in error.lower():
                    return "", "SESSION_NOT_FOUND"
                logger.warning(f"Claude CLI error: {error}")
                return output or error, None
            
            return output or "(응답 없음)", None
            
        except asyncio.TimeoutError:
            logger.error(f"Claude CLI timeout after {self.timeout}s")
            return "", "TIMEOUT"
        except Exception as e:
            logger.exception("Claude CLI error")
            return "", str(e)
    
    def _build_command(
        self,
        message: str,
        session_id: Optional[str],
        resume: bool,
    ) -> list[str]:
        cmd = list(self.command_parts)
        
        if resume and session_id:
            cmd.extend(["--resume", session_id])
        elif session_id:
            cmd.extend(["--session-id", session_id])
        
        cmd.extend([
            "--print",
            "--output-format", "text",
        ])
        
        if self.system_prompt:
            cmd.extend(["--system-prompt", self.system_prompt])
        
        cmd.append(message)
        return cmd
    
    async def summarize(self, questions: list[str], max_questions: int = 10) -> str:
        """Generate a summary of conversation questions."""
        if not questions:
            return "(내용 없음)"
        
        history_text = "\n".join(f"- {q[:100]}" for q in questions[:max_questions])
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
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=60,
            )
            
            summary = stdout.decode("utf-8").strip()
            return summary[:300] if summary else "(요약 실패)"
            
        except Exception:
            first_q = questions[0][:50]
            return f'"{first_q}..."'
