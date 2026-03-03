"""Bot constants and regex patterns."""

import re

# ACTION 패턴 (매니저 세션용)
# 세션 ID는 영숫자만 허용 (8자리)
ACTION_DELETE_PATTERN = re.compile(r'\[ACTION:DELETE:([a-zA-Z0-9]+)\]')
ACTION_RENAME_PATTERN = re.compile(r'\[ACTION:RENAME:([a-zA-Z0-9]+):([^\]]+)\]')
ACTION_CREATE_PATTERN = re.compile(r'\[ACTION:CREATE:(opus|sonnet|haiku):([^\]]+)\]')
ACTION_CREATE_SWITCH_PATTERN = re.compile(r'\[ACTION:CREATE_AND_SWITCH:(opus|sonnet|haiku):([^\]]+)\]')
ACTION_SWITCH_PATTERN = re.compile(r'\[ACTION:SWITCH:([a-zA-Z0-9]+)\]')

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


def remove_action_tags(text: str) -> str:
    """응답에서 모든 ACTION 태그 제거."""
    result = text
    result = ACTION_DELETE_PATTERN.sub('', result)
    result = ACTION_RENAME_PATTERN.sub('', result)
    result = ACTION_CREATE_PATTERN.sub('', result)
    result = ACTION_CREATE_SWITCH_PATTERN.sub('', result)
    result = ACTION_SWITCH_PATTERN.sub('', result)
    return result.strip()
