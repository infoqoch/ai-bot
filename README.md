# Telegram CLI AI Bot

**Claude/Codex CLI를 텔레그램에서. API 키 없이.**

터미널 없이 스마트폰으로 Claude 또는 Codex와 대화하세요.

---

## 왜 이 프로젝트인가?

| | |
|---|---|
| **API 키 불필요** | Claude CLI / Codex CLI 로그인만 되어 있으면 바로 동작 |
| **어디서든** | 출퇴근길, 카페, 침대에서 텔레그램으로 코딩 대화 |
| **멀티 세션** | 프로젝트별 독립 대화, AI/provider별 세션 분리 |
| **AI 매니저** | 자연어로 세션 관리 - "주식돌이 오푸스로 만들어줘" |
| **플러그인** | AI 호출 없이 빠른 응답 - 메모, 날씨 등 확장 가능 |
| **보안** | 허용된 ID만 접근 + 선택적 인증 |

---

## 기술적 하이라이트

### 2-Track 응답 시스템

AI 응답은 느립니다(수십 초~수 분). 모든 요청을 CLI agent에 보내면 사용자 경험이 나빠집니다.

```
사용자 메시지
    │
    ├─▶ [Track 1] 플러그인 매칭 → 즉시 응답 (0.1초)
    │       "메모해줘: 장보기"  → 저장 완료
    │       "서울 날씨"        → Open-Meteo API
    │
    └─▶ [Track 2] Claude/Codex CLI → detached worker 처리 (수십 초)
            "코드 리뷰해줘"    → bot은 즉시 반환, worker가 끝까지 실행
```

플러그인이 처리 가능하면 AI를 호출하지 않아 빠르고, 처리 불가하면 현재 선택된 provider로 넘깁니다.

### 세션별 커스터마이징

세션마다 독립적인 설정이 가능합니다:

| 기능 | 설명 |
|------|------|
| **이름 지정** | `/new opus 코딩도우미` - 세션에 이름 부여 |
| **AI 선택** | `/select_ai`로 Claude/Codex 전환 |
| **모델 선택** | provider별 profile 선택 |
| **모델 변경** | `/model sonnet` - 기존 세션 모델 변경 |
| **세션 전환** | `/s_abc123` - 다른 세션으로 전환 |

### Detached Worker 아키텍처

```
사용자 메시지
    │
    ├─▶ bot (`src.main`)
    │     - 인증/플러그인/세션 결정
    │     - job 저장
    │     - `src.worker_job` spawn
    │     - 즉시 반환
    │
    └─▶ detached worker (`src.worker_job`)
          - provider CLI 실행 owner
          - Telegram 직접 응답
          - 세션 queue drain
```

이 구조 덕분에 Claude나 Codex가 작업 중 `./run.sh restart-soft`를 실행해도, in-flight worker는 살아남아 응답을 끝까지 전송할 가능성이 높습니다. 다만 `stop-hard`/`restart-hard`, host reboot, worker 자체 크래시는 별도입니다.

### ACTION 패턴 시스템

매니저 세션이 자연어를 파싱하여 실제 작업 수행:

```
사용자: "abc123 삭제해줘"
매니저: "삭제할게요! [ACTION:DELETE:abc123]"
봇: [ACTION:DELETE:abc123] 패턴을 파싱하여 세션 삭제 메서드 호출
```

### 보호 메커니즘

| 위협 | 보호 메커니즘 |
|------|---------------|
| 무단 접근 | `ALLOWED_CHAT_IDS` 화이트리스트 |
| 요청 폭주 | 유저별 Semaphore (동시 3개 제한) |
| 좀비 태스크 | Watchdog 루프 (30분 타임아웃, 자동 kill) |
| 파일 손상 | Atomic Write (임시파일 → replace) |

---

## 빠른 시작

### 1. 사전 준비

- **Python 3.11+**
- **Claude CLI** 또는 **Codex CLI** 설치 및 로그인
  ```bash
  claude --version  # Claude 설치 확인
  codex --version   # Codex 설치 확인
  ```

### 2. 텔레그램 봇 생성

1. [@BotFather](https://t.me/BotFather)에서 `/newbot`
2. **API 토큰** 복사

### 3. 설치 및 실행

```bash
git clone https://github.com/infoqoch/telegram-claude-bot.git
cd telegram-claude-bot
python -m venv venv && source venv/bin/activate
pip install -e .

cp .env.example .env
# .env 수정: TELEGRAM_TOKEN, ALLOWED_CHAT_IDS

./run.sh start          # 봇 시작
./run.sh restart-soft   # soft 재시작 (in-flight worker 유지 시도)
./run.sh restart-hard   # hard 재시작 (worker 포함 종료)
./run.sh stop-soft      # supervisor/main만 중지
./run.sh stop-hard      # bot + detached worker 전체 중지
./run.sh status         # 상태 확인
./run.sh log            # 앱 로그 보기
./run.sh log boot       # 부팅/감시 로그 보기
```

> **채팅 ID 확인**: 봇 시작 후 `/chatid` 입력

운영 메모:
- `src.supervisor`는 얇은 프로세스 관리자다. `src.main`만 감시하고 durable state는 들고 있지 않는다.
- 시작 전 설정 preflight에 실패하면 자동 재시작 루프에 들어가지 않고 즉시 중단한다.
- `src.main`이 `CONFIG_ERROR` 또는 `LOCK_HELD`로 종료하면 supervisor는 재시작하지 않는다.
- 짧은 시간 안에 반복 크래시가 누적되면 crash-loop로 보고 자동 재시작을 중단한다.

---

## 사용법

### 기본 대화

메시지를 보내면 현재 선택된 AI가 응답합니다.

### 세션 관리

| 명령어 | 설명 |
|--------|------|
| `/select_ai` | Claude / Codex 선택 |
| `/new opus 프로젝트명` | 새 Opus 세션 (이름 지정) |
| `/session` | 현재 세션 정보 |
| `/session_list` | 전체 세션 목록 |
| `/s_abc123` | 세션 전환 |
| `/model opus` | 모델 변경 |

### 매니저 모드

자연어로 세션 관리:

```
/m                     → 매니저 모드 진입
"주식분석 오푸스로 만들어" → 새 세션 생성
"abc123 삭제해"         → 세션 삭제
```

### 플러그인

AI 호출 없이 즉시 응답:

```
메모해줘: 장보기 목록    → 저장 (즉시)
메모 보여줘             → 조회 (즉시)
서울 날씨               → Open-Meteo API (즉시)
```

> `plugins/custom/`에 직접 플러그인 추가 가능

---

## 문서

| 문서 | 내용 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 개발 규칙, 프로세스 아키텍처, 확장 인터페이스 |
| [docs/SPEC.md](docs/SPEC.md) | UI/UX 기획, 세션/스케줄/재시작 시나리오 |
| [docs/SPEC_PLUGINS_BUILTIN.md](docs/SPEC_PLUGINS_BUILTIN.md) | 빌트인 플러그인 기획 |

---

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TELEGRAM_TOKEN` | (필수) | 봇 토큰 |
| `ALLOWED_CHAT_IDS` | (전체허용) | 허용 채팅 ID |
| `REQUIRE_AUTH` | `true` | 인증 필요 여부 |
| `AUTH_SECRET_KEY` | - | 인증 키 |
| `SESSION_TIMEOUT_HOURS` | `24` | 세션 만료 시간 |
| `SUPERVISOR_CRASH_LOOP_WINDOW_SECONDS` | `300` | crash-loop 판정 시간 창 |
| `SUPERVISOR_CRASH_LOOP_MAX_CRASHES` | `5` | 시간 창 내 허용 크래시 횟수 |

---

## 라이선스

MIT
