"""Bot constants and regex patterns."""

from src.ai import (
    get_profile_badge,
    get_profile_label,
    infer_provider_from_model,
)

# 메시지 제한
MAX_MESSAGE_LENGTH = 4096
MAX_TELEGRAM_MESSAGE = 4000  # 텔레그램 메시지 최대 길이

# Watchdog 설정
WATCHDOG_INTERVAL_SECONDS = 60  # 1분마다 체크
TASK_TIMEOUT_SECONDS = 30 * 60  # 30분 타임아웃

# 장시간 작업 알림 설정
LONG_TASK_THRESHOLD_SECONDS = 5 * 60  # 5분 이상 걸리면 알림

# UI 표시 제한
MAX_TASK_MESSAGE_PREVIEW = 100  # 태스크 메시지 미리보기 최대 길이
MAX_WORKSPACE_PATHS_DISPLAY = 10  # 워크스페이스 경로 목록 최대 표시 개수
MAX_LOCK_STATUS_PREVIEW = 40  # 락 상태 메시지 미리보기 최대 길이
MAX_SESSION_NAME_LENGTH = 50  # 세션 이름 최대 길이

def get_model_emoji(model: str) -> str:
    """모델명에 해당하는 이모지 반환."""
    provider = infer_provider_from_model(model)
    return get_profile_badge(provider, model)


def get_model_badge(model: str) -> str:
    """모델명에 해당하는 뱃지 반환."""
    provider = infer_provider_from_model(model)
    return get_profile_badge(provider, model)


def get_model_label(model: str) -> str:
    """모델명에 해당하는 표시 라벨 반환."""
    provider = infer_provider_from_model(model)
    return get_profile_label(provider, model)
