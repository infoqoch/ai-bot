# 🤖 AI Bot

**Claude Code를 텔레그램에서. API 키 없이.**

터미널 없이 스마트폰으로 Claude Code와 대화하세요.

## ✨ 강점

| | |
|---|---|
| **🔑 API 키 불필요** | Claude CLI만 설치되어 있으면 바로 동작 |
| **📱 어디서든** | 출퇴근길, 카페, 침대에서 텔레그램으로 코딩 |
| **💬 멀티 세션** | 프로젝트별 독립 대화, 언제든 전환 가능 |
| **🔒 내 봇은 나만** | 허용된 ID만 접근 + 선택적 인증 |
| **⚡ 안정적** | 동시 요청 제한, 좀비 태스크 자동 정리 |

## 🚀 5분 설치

```bash
git clone https://github.com/infoqoch/ai-bot.git
cd ai-bot
python -m venv venv && source venv/bin/activate
pip install -e .
cp .env.example .env  # TELEGRAM_TOKEN 설정
./run.sh start
```

## 💬 사용법

```
메시지 보내기     →  Claude 응답
/new              →  새 세션 시작
/session_list     →  세션 목록
/s_abc123         →  세션 전환
/h_abc123         →  히스토리 보기
```

## ⚙️ 필수 설정

| 변수 | 설명 |
|------|------|
| `TELEGRAM_TOKEN` | [@BotFather](https://t.me/BotFather)에서 발급 |
| `ALLOWED_CHAT_IDS` | 허용할 채팅 ID (쉼표 구분) |

<details>
<summary>전체 환경변수</summary>

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `AI_COMMAND` | `claude` | CLI 명령어 |
| `REQUIRE_AUTH` | `true` | 인증 필요 여부 |
| `AUTH_SECRET_KEY` | - | 인증 키 (REQUIRE_AUTH=true 시 필수) |
| `SESSION_TIMEOUT_HOURS` | `24` | 세션 만료 시간 |

</details>

## 📄 라이선스

MIT
