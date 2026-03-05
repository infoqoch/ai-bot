"""Tests for schedule module."""

import json
import pytest
from datetime import datetime, time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from src.schedule import Schedule, ScheduleManager, KST


class TestSchedule:
    """Schedule 데이터클래스 테스트."""

    def test_schedule_creation(self):
        """기본 스케줄 생성."""
        schedule = Schedule(
            id="test123",
            user_id="user1",
            chat_id=12345,
            hour=9,
            minute=30,
            message="Good morning!",
            name="Morning greeting"
        )

        assert schedule.id == "test123"
        assert schedule.user_id == "user1"
        assert schedule.chat_id == 12345
        assert schedule.hour == 9
        assert schedule.minute == 30
        assert schedule.message == "Good morning!"
        assert schedule.name == "Morning greeting"
        assert schedule.type == "claude"
        assert schedule.model == "sonnet"
        assert schedule.enabled is True
        assert schedule.run_count == 0

    def test_schedule_time_str(self):
        """time_str 프로퍼티."""
        schedule = Schedule(
            id="test", user_id="u", chat_id=1,
            hour=9, minute=5, message="", name=""
        )
        assert schedule.time_str == "09:05"

        schedule2 = Schedule(
            id="test", user_id="u", chat_id=1,
            hour=14, minute=30, message="", name=""
        )
        assert schedule2.time_str == "14:30"

    def test_schedule_time(self):
        """schedule_time 프로퍼티."""
        schedule = Schedule(
            id="test", user_id="u", chat_id=1,
            hour=9, minute=30, message="", name=""
        )
        t = schedule.schedule_time
        assert t.hour == 9
        assert t.minute == 30
        assert t.tzinfo == KST

    def test_type_emoji(self):
        """type_emoji 프로퍼티."""
        claude_schedule = Schedule(
            id="test", user_id="u", chat_id=1,
            hour=9, minute=0, message="", name="",
            type="claude"
        )
        assert claude_schedule.type_emoji == "💬"

        workspace_schedule = Schedule(
            id="test", user_id="u", chat_id=1,
            hour=9, minute=0, message="", name="",
            type="workspace"
        )
        assert workspace_schedule.type_emoji == "📁"

    def test_to_dict(self):
        """to_dict 메서드."""
        schedule = Schedule(
            id="test123",
            user_id="user1",
            chat_id=12345,
            hour=9,
            minute=30,
            message="Hello",
            name="Test"
        )
        d = schedule.to_dict()

        assert d["id"] == "test123"
        assert d["user_id"] == "user1"
        assert d["chat_id"] == 12345
        assert d["hour"] == 9
        assert d["minute"] == 30
        assert d["message"] == "Hello"
        assert d["name"] == "Test"
        assert d["type"] == "claude"

    def test_from_dict(self):
        """from_dict 메서드."""
        data = {
            "id": "abc123",
            "user_id": "user2",
            "chat_id": 54321,
            "hour": 18,
            "minute": 45,
            "message": "Evening check",
            "name": "Evening",
            "type": "claude",
            "model": "opus",
            "enabled": False,
        }
        schedule = Schedule.from_dict(data)

        assert schedule.id == "abc123"
        assert schedule.user_id == "user2"
        assert schedule.chat_id == 54321
        assert schedule.hour == 18
        assert schedule.minute == 45
        assert schedule.model == "opus"
        assert schedule.enabled is False

    def test_from_dict_migration_session_based(self):
        """from_dict - 기존 세션 기반 데이터 마이그레이션."""
        data = {
            "id": "old123",
            "user_id": "user1",
            "chat_id": 11111,
            "hour": 8,
            "minute": 0,
            "message": "Wake up",
            "session_id": "old-session-id",  # 기존 세션 기반
            "session_name": "Old Session",
        }
        schedule = Schedule.from_dict(data)

        assert schedule.id == "old123"
        assert schedule.type == "claude"
        assert schedule.name == "Old Session"
        assert schedule.workspace_path is None

    def test_from_dict_migration_project_path(self):
        """from_dict - project_path → workspace_path 마이그레이션."""
        data = {
            "id": "proj123",
            "user_id": "user1",
            "chat_id": 11111,
            "hour": 10,
            "minute": 0,
            "message": "Build",
            "name": "Build Job",
            "type": "project",  # 기존 타입
            "project_path": "/path/to/project",  # 기존 필드명
        }
        schedule = Schedule.from_dict(data)

        assert schedule.type == "workspace"
        assert schedule.workspace_path == "/path/to/project"


class TestScheduleManager:
    """ScheduleManager 테스트."""

    @pytest.fixture
    def temp_data_file(self, tmp_path):
        """임시 데이터 파일 경로."""
        return tmp_path / "schedules.json"

    @pytest.fixture
    def mock_claude_client(self):
        """Mock Claude 클라이언트."""
        return MagicMock()

    def test_init_empty(self, temp_data_file, mock_claude_client):
        """빈 상태로 초기화."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)

        assert len(manager._schedules) == 0
        assert manager.data_file == temp_data_file
        assert manager.claude == mock_claude_client

    def test_init_with_existing_data(self, temp_data_file, mock_claude_client):
        """기존 데이터로 초기화."""
        # 미리 데이터 생성
        temp_data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schedules": [
                {
                    "id": "sched1",
                    "user_id": "user1",
                    "chat_id": 12345,
                    "hour": 9,
                    "minute": 0,
                    "message": "Hello",
                    "name": "Morning",
                    "type": "claude",
                    "model": "sonnet",
                    "enabled": True,
                }
            ]
        }
        with open(temp_data_file, "w") as f:
            json.dump(data, f)

        manager = ScheduleManager(temp_data_file, mock_claude_client)

        assert len(manager._schedules) == 1
        assert "sched1" in manager._schedules
        assert manager._schedules["sched1"].name == "Morning"

    @patch("src.schedule.scheduler_manager")
    def test_add_schedule(self, mock_scheduler, temp_data_file, mock_claude_client):
        """스케줄 추가."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)

        schedule = manager.add(
            user_id="user1",
            chat_id=12345,
            name="Test Schedule",
            hour=10,
            minute=30,
            message="Test message",
        )

        assert schedule.id in manager._schedules
        assert manager._schedules[schedule.id].name == "Test Schedule"
        # 파일에 저장되었는지 확인
        assert temp_data_file.exists()

    @patch("src.schedule.scheduler_manager")
    def test_remove_schedule(self, mock_scheduler, temp_data_file, mock_claude_client):
        """스케줄 삭제."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)

        schedule = manager.add(
            user_id="user1",
            chat_id=12345,
            name="Remove me",
            hour=10,
            minute=0,
            message="",
        )
        assert schedule.id in manager._schedules

        result = manager.remove(schedule.id)
        assert result is True
        assert schedule.id not in manager._schedules

    def test_remove_nonexistent(self, temp_data_file, mock_claude_client):
        """존재하지 않는 스케줄 삭제 시도."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)

        result = manager.remove("nonexistent")
        assert result is False

    @patch("src.schedule.scheduler_manager")
    def test_toggle_schedule(self, mock_scheduler, temp_data_file, mock_claude_client):
        """스케줄 활성화/비활성화 토글."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)

        schedule = manager.add(
            user_id="user1",
            chat_id=12345,
            name="Toggle Test",
            hour=10,
            minute=0,
            message="",
        )

        # 비활성화
        result = manager.toggle(schedule.id)
        assert result is False  # toggle returns new state
        assert manager._schedules[schedule.id].enabled is False

        # 다시 활성화
        result = manager.toggle(schedule.id)
        assert result is True
        assert manager._schedules[schedule.id].enabled is True

    @patch("src.schedule.scheduler_manager")
    def test_list_by_user(self, mock_scheduler, temp_data_file, mock_claude_client):
        """사용자별 스케줄 조회."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)

        # 여러 사용자의 스케줄 추가
        manager.add(
            user_id="user1", chat_id=111,
            name="User1 Schedule1", hour=9, minute=0, message=""
        )
        manager.add(
            user_id="user1", chat_id=111,
            name="User1 Schedule2", hour=10, minute=0, message=""
        )
        manager.add(
            user_id="user2", chat_id=222,
            name="User2 Schedule", hour=11, minute=0, message=""
        )

        user1_schedules = manager.list_by_user("user1")
        assert len(user1_schedules) == 2

        user2_schedules = manager.list_by_user("user2")
        assert len(user2_schedules) == 1

        user3_schedules = manager.list_by_user("user3")
        assert len(user3_schedules) == 0

    @patch("src.schedule.scheduler_manager")
    def test_get_status_text(self, mock_scheduler, temp_data_file, mock_claude_client):
        """스케줄 상태 텍스트."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)

        # 빈 상태
        status = manager.get_status_text("user1")
        assert "등록된 스케줄이 없습니다" in status

        # 스케줄 추가 후
        manager.add(
            user_id="user1", chat_id=111,
            name="Morning Call", hour=9, minute=0, message="Morning"
        )
        status = manager.get_status_text("user1")
        assert "Morning Call" in status
        assert "09:00" in status

    def test_set_bot(self, temp_data_file, mock_claude_client):
        """Bot 설정."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)
        mock_bot = MagicMock()

        manager.set_bot(mock_bot)
        assert manager._bot == mock_bot

    def test_set_claude_client(self, temp_data_file, mock_claude_client):
        """Claude 클라이언트 설정."""
        manager = ScheduleManager(temp_data_file, mock_claude_client)
        new_client = MagicMock()

        manager.set_claude_client(new_client)
        assert manager.claude == new_client

    @patch("src.schedule.scheduler_manager")
    def test_register_all_to_scheduler(self, mock_scheduler_manager, temp_data_file, mock_claude_client):
        """SchedulerManager에 모든 스케줄 등록."""
        mock_scheduler_manager.register_daily.return_value = True

        manager = ScheduleManager(temp_data_file, mock_claude_client)
        s1 = manager.add(
            user_id="user1", chat_id=111,
            name="Schedule 1", hour=9, minute=0, message=""
        )
        s2 = manager.add(
            user_id="user1", chat_id=111,
            name="Schedule 2", hour=10, minute=0, message=""
        )
        # 두 번째 스케줄 비활성화
        manager.toggle(s2.id)

        count = manager.register_all_to_scheduler()

        # 활성화된 스케줄만 등록됨
        assert count == 1
        mock_scheduler_manager.unregister_by_owner.assert_called_once()
        # register_daily는 add에서도 호출되므로 최소 1번 이상 호출됨
        assert mock_scheduler_manager.register_daily.call_count >= 1
