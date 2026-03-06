"""통합 테스트.

실제 앱 시작 및 주요 컴포넌트 통합 검증.
"""

import asyncio
from unittest.mock import patch, MagicMock

import pytest


class TestAppStartup:
    """앱 시작 통합 테스트."""

    @pytest.mark.asyncio
    async def test_create_app_succeeds(self):
        """create_app이 에러 없이 실행되는지 검증."""
        import os
        from src.main import create_app

        # 환경 변수 설정 (pydantic settings 파싱 문제 방지)
        original_env = os.environ.get("ALLOWED_CHAT_IDS")
        os.environ["ALLOWED_CHAT_IDS"] = "[]"

        try:
            # Mock telegram Application to avoid actual API calls
            mock_app = MagicMock()
            mock_app.job_queue = MagicMock()
            mock_app.add_handler = MagicMock()

            with patch("src.main.Application") as MockApplication:
                MockApplication.builder.return_value.token.return_value.build.return_value = mock_app

                # Should not raise any exception
                app = create_app()
                assert app is not None
        finally:
            # 원래 값 복원
            if original_env is not None:
                os.environ["ALLOWED_CHAT_IDS"] = original_env
            elif "ALLOWED_CHAT_IDS" in os.environ:
                del os.environ["ALLOWED_CHAT_IDS"]

    def test_scheduler_manager_has_no_scheduler_attribute(self):
        """SchedulerManager에 scheduler 속성이 없음을 확인.

        main.py에서 scheduler_manager.scheduler로 접근하면 안됨.
        """
        from src.scheduler_manager import SchedulerManager

        # SchedulerManager 클래스 검증 (싱글톤 인스턴스가 아닌 클래스 레벨에서)
        assert hasattr(SchedulerManager, "register_daily")

        # scheduler 속성은 존재하지 않아야 함
        assert not hasattr(SchedulerManager, "scheduler")

    def test_main_py_does_not_use_scheduler_manager_scheduler(self):
        """main.py에서 scheduler_manager.scheduler를 사용하지 않는지 검증."""
        from pathlib import Path

        main_py = Path(__file__).parent.parent / "src" / "main.py"
        content = main_py.read_text()

        # scheduler_manager.scheduler 패턴이 없어야 함
        assert "scheduler_manager.scheduler" not in content
