# 🤖 AI Bot

**Claude Code의 강력함을, 텔레그램에서.**

터미널 없이도 Claude Code CLI의 모든 기능을 텔레그램 메신저에서 사용하세요. 언제 어디서든 스마트폰으로 AI 코딩 어시스턴트와 대화할 수 있습니다.

---

## ✨ 왜 AI Bot인가?

### 🚀 어디서든 Claude Code
터미널이 없어도 괜찮습니다. 출퇴근길, 카페, 침대에서도 텔레그램만 있으면 Claude Code와 대화할 수 있습니다.

### 💬 대화가 끊기지 않는 세션 관리
- **멀티 세션**: 프로젝트별로 독립된 대화 유지
- **세션 전환**: 이전 대화로 언제든 돌아가기
- **24시간 유지**: 세션이 만료되어도 히스토리 보존

### 🔒 내 봇은 나만 사용
- 허용된 채팅 ID만 접근 가능
- 선택적 인증으로 이중 보안
- 비밀키 기반 30분 세션 인증

### ⚡ 빠르고 안정적인 비동기 설계
- 동시 요청도 순차 처리 (데이터 유실 방지)
- 5분 타임아웃으로 무한 대기 없음
- 긴 응답도 자동 분할 전송

---

## 🎯 주요 기능

| 기능 | 설명 |
|------|------|
| **Claude Code 통합** | CLI 명령어 그대로 텔레그램에서 실행 |
| **멀티 세션** | 여러 대화를 독립적으로 관리 |
| **AI 세션 요약** | 각 세션의 내용을 AI가 한 줄로 요약 |
| **세션 전환** | `/s_abc123`으로 이전 대화 이어가기 |
| **선택적 인증** | 필요 시 비밀키 인증 활성화 |
| **개발자 알림** | 변경사항을 텔레그램으로 자동 리포트 |

---

## 🚀 빠른 시작

### 1. 설치
```bash
git clone https://github.com/infoqoch/ai-bot.git
cd ai-bot
python -m venv venv && source venv/bin/activate
pip install -e .
```

### 2. 설정
```bash
cp .env.example .env
# .env 수정: TELEGRAM_TOKEN, ALLOWED_CHAT_IDS 등
```

### 3. 실행
```bash
./run.sh start    # 봇 시작
./run.sh status   # 상태 확인
./run.sh log      # 로그 보기
```

---

## 💬 사용법

### 기본 대화
그냥 메시지를 보내면 됩니다.
```
나: 파이썬으로 피보나치 함수 만들어줘
봇: [Claude Code 응답]
```

### 세션 관리
```
/new              → 새 대화 시작
/session          → 현재 대화 정보
/session_list     → 전체 세션 + AI 요약
/s_abc123         → 특정 세션으로 전환
```

### 인증 (선택)
```
/auth <비밀키>    → 30분간 인증
/status           → 인증 상태 확인
```

---

## ⚙️ 환경변수

| 변수 | 필수 | 기본값 | 설명 |
|------|:----:|--------|------|
| `TELEGRAM_TOKEN` | ✅ | - | 봇 토큰 |
| `ALLOWED_CHAT_IDS` | - | 전체 허용 | 허용 채팅 ID (쉼표 구분) |
| `AI_COMMAND` | - | `claude` | AI CLI 명령어 |
| `REQUIRE_AUTH` | - | `true` | 인증 필요 여부 |
| `AUTH_SECRET_KEY` | 조건부 | - | 인증 키 |

<details>
<summary>전체 환경변수 보기</summary>

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MAINTAINER_CHAT_ID` | - | 개발 알림 수신 ID |
| `SESSION_TIMEOUT_HOURS` | `24` | 세션 만료 시간 |
| `AUTH_TIMEOUT_MINUTES` | `30` | 인증 유효 시간 |

</details>

---

## 🛠️ 개발

```bash
pip install -e ".[dev]"
./run.sh test     # 테스트 실행
```

<details>
<summary>프로젝트 구조</summary>

```
src/
├── main.py           # 엔트리포인트
├── config.py         # Pydantic 설정
├── notify.py         # 개발 알림
├── bot/              # 텔레그램 핸들러
└── claude/           # AI CLI 클라이언트
```

</details>

---

## 📄 라이선스

MIT
