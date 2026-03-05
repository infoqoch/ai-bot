"""Bot constants and regex patterns."""

# 메시지 제한
MAX_MESSAGE_LENGTH = 4096
MAX_TELEGRAM_MESSAGE = 4000  # 텔레그램 메시지 최대 길이

# Watchdog 설정
WATCHDOG_INTERVAL_SECONDS = 60  # 1분마다 체크
TASK_TIMEOUT_SECONDS = 30 * 60  # 30분 타임아웃

# 장시간 작업 알림 설정
LONG_TASK_THRESHOLD_SECONDS = 5 * 60  # 5분 이상 걸리면 알림

# 모델 이모지 매핑
MODEL_EMOJI = {
    "opus": "🧠",
    "sonnet": "⚡",
    "haiku": "🚀",
}


def get_model_emoji(model: str) -> str:
    """모델명에 해당하는 이모지 반환."""
    return MODEL_EMOJI.get(model, "")
