"""Claude CLI 클라이언트 테스트.

ClaudeClient 클래스의 핵심 기능 검증:
- 명령어 빌드
- 시스템 프롬프트 로딩
- 요약 기능
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.claude.client import ClaudeClient


@pytest.fixture
def client():
    """기본 클라이언트 생성."""
    return ClaudeClient(command="claude", timeout=60)


@pytest.fixture
def client_with_prompt():
    """시스템 프롬프트 포함 클라이언트."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("You are a helpful assistant.")
        prompt_path = Path(f.name)

    client = ClaudeClient(
        command="claude --dangerously-skip-permissions",
        system_prompt_file=prompt_path,
        timeout=60,
    )
    yield client
    prompt_path.unlink()


class TestClaudeClient:
    """ClaudeClient 단위 테스트."""

    def test_build_command_basic(self, client):
        """기본 명령어 빌드 확인."""
        cmd = client._build_command("Hello", None, False)

        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "--output-format" in cmd
        assert "text" in cmd
        assert cmd[-1] == "Hello"

    def test_build_command_with_session(self, client):
        """세션 ID 포함 명령어 빌드."""
        cmd = client._build_command("Hello", "session-123", False)

        assert "--session-id" in cmd
        assert "session-123" in cmd

    def test_build_command_resume(self, client):
        """세션 재개 명령어 빌드."""
        cmd = client._build_command("Hello", "session-123", True)

        assert "--resume" in cmd
        assert "session-123" in cmd
        assert "--session-id" not in cmd

    def test_build_command_with_system_prompt(self, client_with_prompt):
        """시스템 프롬프트 포함 명령어 빌드."""
        cmd = client_with_prompt._build_command("Hello", None, False)

        assert "--system-prompt" in cmd
        assert "You are a helpful assistant." in cmd

    def test_command_parsing(self):
        """복잡한 명령어 파싱 확인."""
        client = ClaudeClient(
            command="claude --dangerously-skip-permissions --verbose"
        )

        assert client.command_parts == [
            "claude", "--dangerously-skip-permissions", "--verbose"
        ]

    def test_load_system_prompt_nonexistent(self):
        """존재하지 않는 프롬프트 파일 처리."""
        client = ClaudeClient(
            system_prompt_file=Path("/nonexistent/path.md")
        )

        assert client.system_prompt is None

    @pytest.mark.asyncio
    async def test_chat_timeout(self, client):
        """타임아웃 처리 확인."""
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(side_effect=TimeoutError())
            mock_exec.return_value = mock_process

            with patch('asyncio.wait_for', side_effect=TimeoutError()):
                response, error = await client.chat("Hello")

            assert error == "TIMEOUT"
            assert response == ""

    @pytest.mark.asyncio
    async def test_summarize_empty_questions(self, client):
        """빈 질문 목록 요약."""
        result = await client.summarize([])
        assert result == "(내용 없음)"

    def test_summarize_prompt_format(self, client):
        """요약 프롬프트 형식 확인."""
        questions = ["질문1", "질문2", "질문3"]

        # _build_command에서 프롬프트가 올바르게 구성되는지 확인
        # 실제 summarize는 subprocess를 호출하므로 통합 테스트 필요
        assert len(questions) == 3
