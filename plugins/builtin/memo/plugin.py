"""메모 플러그인 - 버튼 기반 단일 진입점."""

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply

from src.plugins.loader import Plugin, PluginResult


class MemoPlugin(Plugin):
    """버튼 기반 메모 플러그인 - 단일 진입점."""

    name = "memo"
    description = "메모 저장, 조회, 삭제"
    usage = (
        "📝 <b>메모 플러그인</b>\n\n"
        "<code>메모</code> 또는 <code>/memo</code> 입력"
    )

    CALLBACK_PREFIX = "memo:"

    TRIGGER_KEYWORDS = ["메모", "memo"]

    EXCLUDE_PATTERNS = [
        r"(란|이란|가|이)\s*(뭐|무엇|뭔)",
        r"영어로|번역|translate",
        r"어떻게|왜|언제|어디",
        r"알려줘|설명|뜻",
    ]

    async def can_handle(self, message: str, chat_id: int) -> bool:
        """메모 관련 메시지인지 확인."""
        msg = message.strip().lower()

        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                return False

        for keyword in self.TRIGGER_KEYWORDS:
            if msg == keyword:
                return True

        return False

    async def handle(self, message: str, chat_id: int) -> PluginResult:
        """메모 메인 화면 표시."""
        result = self._handle_main(chat_id)
        return PluginResult(
            handled=True,
            response=result["text"],
            reply_markup=result.get("reply_markup")
        )

    def handle_callback(self, callback_data: str, chat_id: int) -> dict:
        """callback_data 처리."""
        parts = callback_data.split(":")
        if len(parts) < 2:
            return {"text": "❌ 잘못된 요청", "edit": True}

        action = parts[1]

        if action == "main":
            return self._handle_main(chat_id)
        elif action == "list":
            return self._handle_list(chat_id)
        elif action == "add":
            return self._handle_add_prompt(chat_id)
        elif action == "del":
            memo_id = int(parts[2]) if len(parts) > 2 else 0
            return self._handle_delete(chat_id, memo_id)
        elif action == "confirm_del":
            memo_id = int(parts[2]) if len(parts) > 2 else 0
            return self._handle_confirm_delete(chat_id, memo_id)
        elif action == "cancel":
            return self._handle_list(chat_id)
        else:
            return {"text": "❌ 알 수 없는 명령", "edit": True}

    def _handle_main(self, chat_id: int) -> dict:
        """메인 메뉴."""
        memos = self.repository.list_memos(chat_id)

        buttons = [
            [
                InlineKeyboardButton("📄 목록", callback_data="memo:list"),
                InlineKeyboardButton("➕ 추가", callback_data="memo:add"),
            ]
        ]

        return {
            "text": f"📝 <b>메모</b>\n\n저장된 메모: {len(memos)}개",
            "reply_markup": InlineKeyboardMarkup(buttons),
            "edit": True,
        }

    def _handle_list(self, chat_id: int) -> dict:
        """메모 목록."""
        memos = self.repository.list_memos(chat_id)

        if not memos:
            buttons = [
                [InlineKeyboardButton("➕ 추가", callback_data="memo:add")],
                [InlineKeyboardButton("⬅️ 뒤로", callback_data="memo:main")],
            ]
            return {
                "text": "📭 저장된 메모가 없습니다.",
                "reply_markup": InlineKeyboardMarkup(buttons),
                "edit": True,
            }

        lines = ["📝 <b>메모 목록</b>\n"]
        buttons = []

        for memo in memos:
            created = memo.created_at[:10]
            content_preview = memo.content[:30] + "..." if len(memo.content) > 30 else memo.content
            lines.append(f"<b>#{memo.id}</b> {memo.content}\n<i>{created}</i>")

            buttons.append([
                InlineKeyboardButton(
                    f"🗑️ #{memo.id} {content_preview[:15]}",
                    callback_data=f"memo:del:{memo.id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton("➕ 추가", callback_data="memo:add"),
            InlineKeyboardButton("🔄 새로고침", callback_data="memo:list"),
        ])
        buttons.append([
            InlineKeyboardButton("⬅️ 뒤로", callback_data="memo:main"),
        ])

        return {
            "text": "\n".join(lines),
            "reply_markup": InlineKeyboardMarkup(buttons),
            "edit": True,
        }

    def _handle_add_prompt(self, chat_id: int) -> dict:
        """메모 추가 - ForceReply."""
        return {
            "text": "📝 <b>메모 추가</b>\n\n아래에 메모 내용을 입력하세요.",
            "force_reply": ForceReply(
                selective=True,
                input_field_placeholder="메모 내용 입력..."
            ),
            "force_reply_marker": "memo_add",
            "edit": False,
        }

    def _handle_delete(self, chat_id: int, memo_id: int) -> dict:
        """삭제 확인."""
        memo = self.repository.get_memo(memo_id)

        if not memo:
            return {"text": f"❌ 메모 #{memo_id}을(를) 찾을 수 없습니다.", "edit": True}

        keyboard = [
            [
                InlineKeyboardButton("✅ 삭제", callback_data=f"memo:confirm_del:{memo_id}"),
                InlineKeyboardButton("❌ 취소", callback_data="memo:cancel"),
            ]
        ]

        return {
            "text": f"🗑️ <b>삭제 확인</b>\n\n<b>#{memo.id}</b> {memo.content}\n\n정말 삭제?",
            "reply_markup": InlineKeyboardMarkup(keyboard),
            "edit": True,
        }

    def _handle_confirm_delete(self, chat_id: int, memo_id: int) -> dict:
        """삭제 실행."""
        memo = self.repository.get_memo(memo_id)

        if not memo:
            return {"text": f"❌ 메모 #{memo_id}을(를) 찾을 수 없습니다.", "edit": True}

        content = memo.content
        self.repository.delete_memo(memo_id)

        result = self._handle_list(chat_id)
        result["text"] = f"🗑️ 삭제됨: <s>{content[:20]}</s>\n\n" + result["text"]
        return result

    def handle_force_reply(self, message: str, chat_id: int) -> dict:
        """ForceReply 응답 처리 - 메모 추가."""
        content = message.strip()

        if not content:
            return {
                "text": "❌ 메모 내용이 비어있습니다.",
                "reply_markup": InlineKeyboardMarkup([[
                    InlineKeyboardButton("📝 다시 시도", callback_data="memo:add"),
                ]]),
            }

        memo = self.repository.add_memo(chat_id, content)

        keyboard = [
            [
                InlineKeyboardButton("📄 목록", callback_data="memo:list"),
                InlineKeyboardButton("➕ 추가", callback_data="memo:add"),
            ]
        ]

        return {
            "text": f"✅ 메모 저장됨!\n\n<b>#{memo.id}</b> {content}",
            "reply_markup": InlineKeyboardMarkup(keyboard),
        }
