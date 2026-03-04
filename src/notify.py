"""Development notification utility."""

import asyncio
import httpx
from typing import Optional

from src.config import get_settings


async def send_dev_report(
    changes: list[str],
    files: list[str],
    test_passed: bool = True,
    extra_message: str = "",
) -> bool:
    """Send development completion report to admin."""
    settings = get_settings()

    if not settings.admin_chat_id:
        print("⚠️ ADMIN_CHAT_ID not set, skipping notification")
        return False

    changes_text = "\n".join(f"• {c}" for c in changes) if changes else "• (없음)"
    files_text = "\n".join(f"• {f}" for f in files) if files else "• (없음)"
    test_status = "✅ 통과" if test_passed else "❌ 실패"

    message = f"""🔧 <b>개발 완료 리포트</b>

📝 <b>변경사항:</b>
{changes_text}

📁 <b>수정된 파일:</b>
{files_text}

🧪 <b>테스트:</b> {test_status}
🚀 <b>상태:</b> 배포 완료"""

    if extra_message:
        message += f"\n\n💬 {extra_message}"

    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    payload = {
        "chat_id": settings.admin_chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        return response.status_code == 200


def notify_sync(
    changes: list[str],
    files: list[str],
    test_passed: bool = True,
    extra_message: str = "",
) -> bool:
    """Synchronous wrapper for send_dev_report."""
    return asyncio.run(send_dev_report(changes, files, test_passed, extra_message))


# CLI usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.notify 'change1' 'change2' -- 'file1' 'file2'")
        sys.exit(1)
    
    args = sys.argv[1:]
    
    # Split by --
    if "--" in args:
        sep_idx = args.index("--")
        changes = args[:sep_idx]
        files = args[sep_idx + 1:]
    else:
        changes = args
        files = []
    
    success = notify_sync(changes, files)
    print("✅ 리포트 전송 완료" if success else "❌ 리포트 전송 실패")
