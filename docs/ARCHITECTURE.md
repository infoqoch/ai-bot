# 아키텍처 및 설계 결정

> 이 문서는 시스템의 내부 구조와 설계 결정 과정을 설명합니다.

---

## 1. 시스템 개요

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  Telegram   │────▶│   Bot (Python)  │────▶│ Claude CLI  │
│   Client    │◀────│                 │◀────│  (Local)    │
└─────────────┘     └─────────────────┘     └─────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ sessions.json │
                    └───────────────┘
```

### 핵심 설계 원칙

| 원칙 | 설명 |
|------|------|
| **CLI 래퍼** | Claude API 직접 호출 ❌, CLI subprocess 실행 ✅ |
| **Fire-and-Forget** | 핸들러는 즉시 반환, 응답은 백그라운드에서 전송 |
| **세션 = Claude session_id** | 자체 UUID 생성 ❌, Claude의 session_id를 그대로 사용 |

---

## 2. 핵심 컴포넌트

### 2.1 BotHandlers (`src/bot/handlers.py`)

텔레그램 메시지를 처리하는 핸들러 클래스.

```python
class BotHandlers:
    _user_locks: dict[str, Lock]        # 세션 생성 시 Race Condition 방지
    _user_semaphores: dict[str, Semaphore]  # 동시 요청 제한 (최대 3개)
    _active_tasks: dict[int, TaskInfo]  # 실행 중인 태스크 추적
    _watchdog_task: Task                # 좀비 태스크 정리 루프
```

### 2.2 ClaudeClient (`src/claude/client.py`)

Claude CLI를 비동기로 실행하는 클라이언트.

```python
class ClaudeClient:
    async def chat(message, session_id) -> ChatResponse
    async def create_session() -> str  # 새 세션 생성
    async def summarize(questions) -> str  # AI 요약
```

### 2.3 SessionStore (`src/claude/session.py`)

세션 데이터를 JSON 파일로 관리.

```python
# 데이터 구조
{
    "user_id": {
        "current": "claude_session_id",
        "sessions": {
            "claude_session_id": {
                "created_at": "...",
                "last_used": "...",
                "history": ["질문1", "질문2"]
            }
        }
    }
}
```

---

## 3. 해결한 문제들

### 3.1 Race Condition - 세션 중복 생성

**문제:** 동일 유저가 빠르게 메시지 2개를 보내면 세션이 2개 생성됨

```
메시지1 ──▶ 세션 없음? ──▶ 세션 생성 (A)
메시지2 ──▶ 세션 없음? ──▶ 세션 생성 (B)  ← 중복!
```

**해결:** 유저별 Lock으로 세션 결정 구간 보호

```python
async with self._user_locks[user_id]:
    session_id = self.sessions.get_current_session_id(user_id)
    if not session_id:
        session_id = await self.claude.create_session()
        self.sessions.create_session(user_id, session_id, message)
```

### 3.2 핸들러 블로킹 - 응답 지연

**문제:** Claude 응답(수 분)을 기다리는 동안 다른 메시지 처리 불가

**해결:** Fire-and-Forget 패턴

```python
# 핸들러는 즉시 반환
asyncio.create_task(self._process_claude_request(...))

# 백그라운드에서 처리 후 chat_id로 직접 응답
async def _process_claude_request(self, bot, chat_id, ...):
    response = await self.claude.chat(message, session_id)
    await bot.send_message(chat_id=chat_id, text=response)
```

### 3.3 좀비 태스크 - 리소스 누수

**문제:** 장시간 실행되는 태스크가 정리되지 않음

**해결:** Watchdog 루프 (1분마다 체크, 30분 초과 시 kill)

```python
async def _watchdog_loop(self):
    while True:
        await asyncio.sleep(60)
        for task_id, info in self._active_tasks.items():
            if time.time() - info.started_at > 30 * 60:
                info.task.cancel()
                await self._kill_claude_process(info.session_id)
```

### 3.4 동시 요청 폭주 - DoS

**문제:** 악의적 사용자가 메시지 폭탄 전송

**해결:** 유저별 Semaphore로 동시 3개 제한

```python
async with self._user_semaphores[user_id]:
    await self._process_claude_request(...)
```

### 3.5 파일 I/O 충돌 - 데이터 손상

**문제:** 동시 저장 시 JSON 파일 손상 가능

**해결:** Atomic Write (임시 파일 → replace)

```python
def _save(self):
    temp_file = self.file_path.with_suffix('.tmp')
    with open(temp_file, "w") as f:
        json.dump(self._data, f)
    temp_file.replace(self.file_path)  # 원자적 교체
```

---

## 4. 보호 메커니즘 요약

| 계층 | 위협 | 보호 |
|------|------|------|
| 접근 | 무단 사용 | `ALLOWED_CHAT_IDS` |
| 인증 | 권한 탈취 | `AuthManager` (30분 TTL) |
| 동시성 | Race Condition | `_user_locks` |
| 리소스 | 요청 폭주 | `_user_semaphores` (3개) |
| 리소스 | 좀비 태스크 | Watchdog (30분) |
| 데이터 | 파일 손상 | Atomic Write |
| DoS | 긴 메시지 | `MAX_MESSAGE_LENGTH` (4096) |

---

## 5. 테스트

```bash
./run.sh test  # 100개 테스트 실행
```

### 테스트 범위

| 모듈 | 테스트 수 | 주요 검증 |
|------|----------|----------|
| `test_session.py` | 21 | Atomic write, datetime 파싱, 세션 관리 |
| `test_client.py` | 22 | ChatResponse, 타임아웃, JSON 파싱 |
| `test_middleware.py` | 30 | 인증, 데코레이터, 만료 정리 |
| `test_handlers.py` | 24 | Fire-and-Forget, Lock, 메시지 분할 |
| `test_formatters.py` | 11 | HTML 변환, 메시지 자르기 |

---

## 6. 의도적으로 구현하지 않은 것

| 항목 | 이유 |
|------|------|
| **CLI 인젝션 방지** | `subprocess_exec`는 shell=False 기본, 이미 안전 |
| **Lock 메모리 정리** | Lock 객체 수십 바이트, ALLOWED_CHAT_IDS로 제한됨 |
| **세션 암호화** | 개인 봇, 서버 접근자 = 운영자 본인 |
| **Graceful Shutdown** | 재시작 빈도 낮음, 필요 시 TODO.md 참조 |
