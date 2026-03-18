# Telegram Agent Relay

**로컬 AI coding agent를 텔레그램으로 원격 제어하세요.**

Claude Code와 Codex 같은 로컬 AI coding agent를 스마트폰에서 관리합니다. 기존 CLI 로그인/구독을 재사용하고, API를 직접 붙이지 않아도 세션 관리, 빠른 플러그인 작업, 장기 실행 작업 추적까지 이어갈 수 있습니다.

---

## 왜 이 프로젝트인가?

| | |
|---|---|
| **기존 CLI 재사용** | Claude Code / Codex CLI 로그인 상태만 있으면 바로 동작 |
| **API 직접 연동 부담 감소** | API 키, 별도 과금 흐름, 프록시 레이어 없이 시작 가능 |
| **원격 제어** | 출퇴근길, 카페, 침대에서 텔레그램으로 로컬 AI agent 세션 관리 |
| **멀티 세션** | 프로젝트별 독립 대화, agent/provider별 세션 분리 |
| **장기 작업 대응** | detached worker로 오래 걸리는 코딩 작업도 끝까지 전달 |
| **플러그인 fast-path** | AI 호출 없이 메모, 날씨 등 즉시 응답 작업 처리 |
| **보안** | 허용된 ID만 접근 + 선택적 인증 |

---

## 기술적 하이라이트

### 2-Track 응답 시스템

AI coding agent 응답은 느립니다(수십 초~수 분). 모든 요청을 agent에 보내면 사용자 경험이 나빠집니다.

```
사용자 메시지
    │
    ├─▶ [Track 1] 플러그인 매칭 → 즉시 응답 (0.1초)
    │       "메모해줘: 장보기"  → 저장 완료
    │       "서울 날씨"        → Open-Meteo API
    │
    └─▶ [Track 2] AI coding agent (Claude Code / Codex CLI) → detached worker 처리 (수십 초)
            "코드 리뷰해줘"    → bot은 즉시 반환, worker가 끝까지 실행
```

플러그인이 처리 가능하면 AI agent를 호출하지 않아 빠르고, 처리 불가하면 현재 선택된 provider로 넘깁니다.

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
- **Claude Code** 또는 **Codex CLI** 설치 및 로그인
  ```bash
  claude --version  # Claude Code 설치 확인
  codex --version   # Codex 설치 확인
  ```

### 2. 텔레그램 봇 생성

1. [@BotFather](https://t.me/BotFather)에서 `/newbot`
2. **API 토큰** 복사

커맨드 메뉴는 봇 시작 시 `setMyCommands`로 자동 동기화됩니다.

- 공개 slash command picker: `/menu`, `/session`, `/new`, `/sl`, `/tasks`
- 나머지 기능은 `/menu` 버튼 허브 또는 직접 명령 입력으로 접근

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

### 메인 진입점

`/menu`가 기본 런처입니다.

- 세션/AI 제어
- 워크스페이스 허브
- 스케줄러 허브
- 플러그인 허브
- `/help` 진입

텔레그램 slash command picker에는 아래 5개만 노출됩니다.

| 명령어 | 설명 |
|--------|------|
| `/menu` | 메인 서비스 메뉴 |
| `/session` | 현재 세션 정보 |
| `/new` | 새 세션 생성 |
| `/sl` | 세션 목록 |
| `/tasks` | 활성 태스크 확인 |

### 기본 대화

메시지를 보내면 현재 선택된 AI가 응답합니다.

AI 응답 하단에는 `Session` 버튼만 붙습니다. 세션 상세로 이동하는 최소 shortcut만 유지합니다.

### 세션 관리

| 명령어 | 설명 |
|--------|------|
| `/menu` | 버튼 기반 허브 열기 |
| `/select_ai` | Claude / Codex 선택 |
| `/new opus 프로젝트명` | 새 Opus 세션 (이름 지정) |
| `/session` | 현재 세션 정보 |
| `/sl` | 전체 세션 목록 |
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

`/plugins` 또는 `/menu -> Plugins`로 버튼 기반 플러그인 허브를 엽니다.

- 목록 본문은 `Builtin` / `Custom` 한 줄 요약으로 표시
- 실제 실행은 동적 버튼으로 처리
- 플러그인 상세 문서는 `/help_extend` 또는 `/help_<plugin>` 사용
- `/memo` 같은 직접 명령은 실행 설명 대신 `/help_memo` 같은 문서 경로로 안내

예시:

```
/plugins                → 플러그인 버튼 허브
/help_extend            → 확장 도움말 인덱스
/help_memo              → Memo 플러그인 상세 도움말
```

> `plugins/custom/`에 직접 플러그인 추가 가능

### 스케줄러

`/scheduler`로 스케줄 허브를 엽니다.

- `💬 Chat`: 현재 선택된 AI/provider 기준 일반 스케줄
- `📂 Workspace`: 워크스페이스 컨텍스트 포함 스케줄
- `🔌 Plugin`: 플러그인 액션 스케줄

기본 UI 플로우:

```text
시간(00~23) → 분(5분 단위) → Daily / One-time → 나머지 입력 → 등록
```

- 목록은 `다음 실행 시각(next run)` 기준으로 정렬됩니다.
- 기본 UI는 `Daily`와 `One-time`만 직접 노출합니다.
- 더 복잡한 반복식은 나중에 AI/admin 경로에서 `cron` 값 업데이트로 처리하는 구조입니다.
- 앱 전체 스케줄 시간 해석은 `APP_TIMEZONE` 하나만 사용합니다. 기본값은 `Asia/Seoul`입니다.

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
| `APP_TIMEZONE` | `Asia/Seoul` | 앱 전체 로컬 시간대. 스케줄/날짜 계산 공통 기준 |
| `REQUIRE_AUTH` | `true` | 인증 필요 여부 |
| `AUTH_SECRET_KEY` | - | 인증 키 |
| `SESSION_TIMEOUT_HOURS` | `24` | 세션 만료 시간 |
| `SUPERVISOR_CRASH_LOOP_WINDOW_SECONDS` | `300` | crash-loop 판정 시간 창 |
| `SUPERVISOR_CRASH_LOOP_MAX_CRASHES` | `5` | 시간 창 내 허용 크래시 횟수 |

---

## 라이선스

MIT
