"""Todo 플러그인 테스트 - Repository 기반."""

import pytest
import tempfile
from pathlib import Path
from datetime import date

from src.repository import init_repository, shutdown_repository, reset_connection
from plugins.builtin.todo.plugin import TodoPlugin


@pytest.fixture
def repo_and_plugin():
    """Repository와 TodoPlugin 설정."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        repo = init_repository(db_path)

        plugin = TodoPlugin()
        plugin._repository = repo

        yield repo, plugin

        shutdown_repository()
        reset_connection()


class TestTodoRepository:
    """Repository 기반 Todo 테스트."""

    def test_add_todo(self, repo_and_plugin):
        """할일 추가."""
        repo, _ = repo_and_plugin
        today = date.today().isoformat()

        todo = repo.add_todo(123, today, "morning", "회의하기")

        assert todo.id > 0
        assert todo.text == "회의하기"
        assert todo.slot == "morning"
        assert todo.done is False

    def test_list_todos_by_date(self, repo_and_plugin):
        """날짜별 할일 조회."""
        repo, _ = repo_and_plugin
        today = date.today().isoformat()

        repo.add_todo(123, today, "morning", "회의")
        repo.add_todo(123, today, "afternoon", "점심")

        todos = repo.list_todos_by_date(123, today)

        assert len(todos) == 2

    def test_mark_todo_done(self, repo_and_plugin):
        """할일 완료 처리."""
        repo, _ = repo_and_plugin
        today = date.today().isoformat()

        todo = repo.add_todo(123, today, "morning", "회의")
        result = repo.mark_todo_done(todo.id)

        assert result is True
        updated = repo.get_todo(todo.id)
        assert updated.done is True

    def test_delete_todo(self, repo_and_plugin):
        """할일 삭제."""
        repo, _ = repo_and_plugin
        today = date.today().isoformat()

        todo = repo.add_todo(123, today, "morning", "회의")
        result = repo.delete_todo(todo.id)

        assert result is True
        assert repo.get_todo(todo.id) is None

    def test_get_pending_todos(self, repo_and_plugin):
        """미완료 할일 조회."""
        repo, _ = repo_and_plugin
        today = date.today().isoformat()

        todo1 = repo.add_todo(123, today, "morning", "회의")
        todo2 = repo.add_todo(123, today, "morning", "이메일")
        repo.mark_todo_done(todo1.id)

        pending = repo.get_pending_todos(123, today)

        assert len(pending) == 1
        assert pending[0].text == "이메일"

    def test_move_todos_to_date(self, repo_and_plugin):
        """할일 날짜 이동."""
        repo, _ = repo_and_plugin
        today = date.today().isoformat()
        tomorrow = "2099-12-31"

        todo = repo.add_todo(123, today, "morning", "회의")
        count = repo.move_todos_to_date([todo.id], tomorrow)

        assert count == 1
        moved = repo.get_todo(todo.id)
        assert moved.date == tomorrow

    def test_get_todo_stats(self, repo_and_plugin):
        """할일 통계."""
        repo, _ = repo_and_plugin
        today = date.today().isoformat()

        todo1 = repo.add_todo(123, today, "morning", "회의")
        repo.add_todo(123, today, "afternoon", "점심")
        repo.mark_todo_done(todo1.id)

        stats = repo.get_todo_stats(123, today)

        assert stats["total"] == 2
        assert stats["done"] == 1
        assert stats["pending"] == 1


class TestTodoPlugin:
    """TodoPlugin 테스트."""

    @pytest.mark.asyncio
    async def test_can_handle_keywords(self, repo_and_plugin):
        """트리거 키워드 인식."""
        _, plugin = repo_and_plugin

        assert await plugin.can_handle("할일", 123) is True
        assert await plugin.can_handle("todo", 123) is True
        assert await plugin.can_handle("투두", 123) is True

    @pytest.mark.asyncio
    async def test_can_handle_exclude_patterns(self, repo_and_plugin):
        """제외 패턴 - AI에게 넘김."""
        _, plugin = repo_and_plugin

        assert await plugin.can_handle("할일이란 뭐야", 123) is False
        assert await plugin.can_handle("할일 영어로", 123) is False

    @pytest.mark.asyncio
    async def test_handle_returns_list(self, repo_and_plugin):
        """handle 실행 시 리스트 반환."""
        _, plugin = repo_and_plugin

        result = await plugin.handle("할일", 123)

        assert result.handled is True
        assert "할일" in result.response

    def test_callback_list_empty(self, repo_and_plugin):
        """콜백: 빈 리스트."""
        _, plugin = repo_and_plugin

        result = plugin.handle_callback("td:list", 123)

        assert "등록된 할일이 없어요" in result["text"]

    def test_callback_add_menu(self, repo_and_plugin):
        """콜백: 추가 메뉴."""
        _, plugin = repo_and_plugin

        result = plugin.handle_callback("td:add", 123)

        assert "시간대 선택" in result["text"]

    def test_callback_add_slot_force_reply(self, repo_and_plugin):
        """콜백: 슬롯 선택 후 ForceReply."""
        _, plugin = repo_and_plugin

        result = plugin.handle_callback("td:add_slot:m", 123)

        assert "force_reply" in result
        assert result["slot_code"] == "m"

    def test_force_reply_add_todos(self, repo_and_plugin):
        """ForceReply로 할일 추가."""
        repo, plugin = repo_and_plugin

        result = plugin.handle_force_reply("회의하기\n이메일 확인", 123, "m")

        assert "2개 추가됨" in result["text"]

        today = date.today().isoformat()
        todos = repo.list_todos_by_date(123, today)
        assert len(todos) == 2

    def test_callback_done(self, repo_and_plugin):
        """콜백: 완료 처리."""
        repo, plugin = repo_and_plugin
        today = date.today().isoformat()

        todo = repo.add_todo(123, today, "morning", "회의")
        result = plugin.handle_callback(f"td:done:{todo.id}", 123)

        assert "완료 처리됨" in result["text"]
        updated = repo.get_todo(todo.id)
        assert updated.done is True

    def test_callback_delete(self, repo_and_plugin):
        """콜백: 삭제."""
        repo, plugin = repo_and_plugin
        today = date.today().isoformat()

        todo = repo.add_todo(123, today, "morning", "회의")
        result = plugin.handle_callback(f"td:del:{todo.id}", 123)

        assert "삭제됨" in result["text"]
        assert repo.get_todo(todo.id) is None

    def test_callback_move_slot(self, repo_and_plugin):
        """콜백: 시간대 이동."""
        repo, plugin = repo_and_plugin
        today = date.today().isoformat()

        todo = repo.add_todo(123, today, "morning", "회의")
        result = plugin.handle_callback(f"td:move:{todo.id}:a", 123)

        assert "오후" in result["text"]

        # 원래 todo는 삭제되고 새로 생성됨
        todos = repo.list_todos_by_slot(123, today, "afternoon")
        assert len(todos) == 1
        assert todos[0].text == "회의"

    def test_callback_tomorrow(self, repo_and_plugin):
        """콜백: 내일로 이동."""
        repo, plugin = repo_and_plugin
        today = date.today().isoformat()

        todo = repo.add_todo(123, today, "morning", "회의")
        result = plugin.handle_callback(f"td:tomorrow:{todo.id}", 123)

        assert "내일로 이동" in result["text"]

        # 날짜가 변경됨
        updated = repo.get_todo(todo.id)
        assert updated.date != today

    def test_multi_select_flow(self, repo_and_plugin):
        """멀티 선택 플로우."""
        repo, plugin = repo_and_plugin
        today = date.today().isoformat()

        todo1 = repo.add_todo(123, today, "morning", "회의")
        todo2 = repo.add_todo(123, today, "morning", "이메일")

        # 멀티 선택 모드 진입
        result = plugin.handle_callback("td:multi", 123)
        assert "멀티 선택" in result["text"]

        # 항목 선택
        result = plugin.handle_callback(f"td:multi_toggle:{todo1.id}", 123)
        assert "1개 선택됨" in result["text"]

        # 선택 항목 완료
        result = plugin.handle_callback("td:multi_done", 123)
        assert "1개 완료" in result["text"]

        # todo1만 완료됨
        assert repo.get_todo(todo1.id).done is True
        assert repo.get_todo(todo2.id).done is False

    def test_date_view(self, repo_and_plugin):
        """날짜별 조회."""
        _, plugin = repo_and_plugin

        result = plugin.handle_callback("td:date:2099-12-31", 123)

        assert "2099-12-31" in result["text"]

    def test_week_view(self, repo_and_plugin):
        """주간 뷰."""
        _, plugin = repo_and_plugin

        result = plugin.handle_callback("td:week:2099-12-31", 123)

        assert "주간 할일" in result["text"]
