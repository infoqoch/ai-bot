#!/usr/bin/env python3
"""실제 Telegram API를 사용한 통합 테스트.

이 파일은 .data/ 폴더에 있어 커밋되지 않음.
ADMIN_CHAT_ID 환경변수가 필요함.

사용법:
    source venv/bin/activate
    python .data/real_integration_test.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import httpx


class RealIntegrationTest:
    """실제 Telegram Bot API를 사용한 통합 테스트."""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("ADMIN_CHAT_ID")

        if not self.token:
            raise ValueError("TELEGRAM_TOKEN 환경변수가 필요합니다")
        if not self.chat_id:
            raise ValueError("ADMIN_CHAT_ID 환경변수가 필요합니다")

        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.results = []

    async def send_message(self, text: str) -> dict:
        """메시지 전송."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            )
            return resp.json()

    async def send_command(self, command: str) -> dict:
        """명령어 전송."""
        return await self.send_message(f"/{command}")

    def log(self, test_name: str, success: bool, message: str = ""):
        """테스트 결과 로깅."""
        status = "✅" if success else "❌"
        result = f"{status} {test_name}"
        if message:
            result += f" - {message}"
        print(result)
        self.results.append((test_name, success, message))

    async def run_all_tests(self):
        """모든 테스트 실행."""
        print("\n" + "="*60)
        print("실제 Telegram API 통합 테스트")
        print("="*60 + "\n")

        # 테스트 시작 알림
        await self.send_message("🧪 <b>통합 테스트 시작</b>")

        # 테스트 실행
        await self.test_help_command()
        await asyncio.sleep(1)

        await self.test_status_command()
        await asyncio.sleep(1)

        await self.test_session_list()
        await asyncio.sleep(1)

        await self.test_plugins_command()
        await asyncio.sleep(1)

        await self.test_scheduler_command()
        await asyncio.sleep(1)

        await self.test_workspace_command()
        await asyncio.sleep(1)

        await self.test_lock_command()
        await asyncio.sleep(1)

        await self.test_jobs_command()
        await asyncio.sleep(1)

        # 결과 요약
        await self.send_summary()

    async def test_help_command(self):
        """도움말 명령어 테스트."""
        try:
            result = await self.send_command("help")
            success = result.get("ok", False)
            self.log("help 명령어", success)
        except Exception as e:
            self.log("help 명령어", False, str(e))

    async def test_status_command(self):
        """상태 명령어 테스트."""
        try:
            result = await self.send_command("status")
            success = result.get("ok", False)
            self.log("status 명령어", success)
        except Exception as e:
            self.log("status 명령어", False, str(e))

    async def test_session_list(self):
        """세션 목록 테스트."""
        try:
            result = await self.send_command("session_list")
            success = result.get("ok", False)
            self.log("session_list 명령어", success)
        except Exception as e:
            self.log("session_list 명령어", False, str(e))

    async def test_plugins_command(self):
        """플러그인 목록 테스트."""
        try:
            result = await self.send_command("plugins")
            success = result.get("ok", False)
            self.log("plugins 명령어", success)
        except Exception as e:
            self.log("plugins 명령어", False, str(e))

    async def test_scheduler_command(self):
        """스케줄러 명령어 테스트."""
        try:
            result = await self.send_command("scheduler")
            success = result.get("ok", False)
            self.log("scheduler 명령어", success)
        except Exception as e:
            self.log("scheduler 명령어", False, str(e))

    async def test_workspace_command(self):
        """워크스페이스 명령어 테스트."""
        try:
            result = await self.send_command("workspace")
            success = result.get("ok", False)
            self.log("workspace 명령어", success)
        except Exception as e:
            self.log("workspace 명령어", False, str(e))

    async def test_lock_command(self):
        """락 명령어 테스트."""
        try:
            result = await self.send_command("lock")
            success = result.get("ok", False)
            self.log("lock 명령어", success)
        except Exception as e:
            self.log("lock 명령어", False, str(e))

    async def test_jobs_command(self):
        """작업 명령어 테스트."""
        try:
            result = await self.send_command("jobs")
            success = result.get("ok", False)
            self.log("jobs 명령어", success)
        except Exception as e:
            self.log("jobs 명령어", False, str(e))

    async def send_summary(self):
        """테스트 결과 요약 전송."""
        total = len(self.results)
        passed = sum(1 for _, success, _ in self.results if success)
        failed = total - passed

        lines = [
            "🧪 <b>통합 테스트 완료</b>",
            "",
            f"📊 결과: {passed}/{total} 통과",
            ""
        ]

        for name, success, msg in self.results:
            status = "✅" if success else "❌"
            line = f"{status} {name}"
            if msg:
                line += f" ({msg})"
            lines.append(line)

        await self.send_message("\n".join(lines))

        print("\n" + "="*60)
        print(f"테스트 완료: {passed}/{total} 통과")
        print("="*60)


async def main():
    try:
        tester = RealIntegrationTest()
        await tester.run_all_tests()
    except ValueError as e:
        print(f"❌ 설정 오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
