# 세션 관리 시스템 분석

> **문서 상태:** v2.0 (2026-03-02 업데이트)
>
> 이전 버전에서 지적된 Race Condition 및 세션 유실 문제는 **모두 해결됨**.
> 현재 문서는 해결된 문제와 남은 개선 과제를 정리합니다.

---

## 1. 아키텍처 변경 요약

### 이전 아키텍처 (문제 있었음)
```
[자체 UUID 생성] → [Claude 호출] → [claude_session_id를 current 세션에 저장]
                                    ↑
                                 Race Condition 발생!
```

### 현재 아키텍처 (해결됨)
```
[Claude session_id 획득] → [그것을 primary key로 저장]
         ↓
    유저별 Lock으로 보호
```

| 항목 | 이전 | 현재 |
|------|------|------|
| Primary Key | 자체 UUID | Claude's session_id |
| Lock 단위 | 세션별 (`_session_locks`) | 유저별 (`_user_locks`) |
| claude_session_id 저장 | `set_claude_session_id()` | 불필요 (PK가 곧 session_id) |
| 메시지 추가 | `current` 참조 | 명시적 session_id 전달 |

---

## 2. 해결된 문제들 (v1.0에서 지적됨)

### 2.1 Race Condition - 세션 생성 동시 호출

**이전 문제:**
```python
# Lock 없이 세션 조회 → 생성
session_id = get_current_session_id(user_id)  # ① 조회
if not session_id:
    session_id = create_session(user_id, message)  # ② 동시 생성 가능!
```

**현재 해결:**
```python
# handlers.py:319-337
async with self._user_locks[user_id]:  # 유저별 Lock
    session_id = self.sessions.get_current_session_id(user_id)
    if not session_id:
        session_id = await self.claude.create_session()
        self.sessions.create_session(user_id, session_id, message)
```

### 2.2 `current` 덮어쓰기 문제

**이전 문제:**
```
Handler A: create_session → current=A
Handler B: create_session → current=B (A 덮어씀!)
```

**현재 해결:** 유저별 Lock으로 동일 유저의 동시 세션 생성 자체가 불가능.

### 2.3 `set_claude_session_id()` 타이밍 문제

**이전 문제:**
```
1. 세션 A 생성, current=A
2. Claude 처리 중...
3. 세션 B 생성, current=B
4. 응답 도착 → set_claude_session_id()가 current(=B)에 저장 ❌
```

**현재 해결:** 메서드 자체가 제거됨. Claude session_id를 primary key로 사용하므로 저장할 필요가 없음.

### 2.4 Map 세션 유실

**이전 문제:** `add_message()`가 `current`를 참조해서 엉뚱한 세션에 저장

**현재 해결:**
```python
# session.py:93-95 - 명시적 session_id 사용
def add_message(self, user_id: str, session_id: str, message: str) -> None:
    """Add a message to specific session (not current!)."""
```

---

## 3. 현재 데이터 구조

```python
# session.py - SessionStore
{
    "user_id": {
        "current": "claude_session_id",  # Claude's session_id 직접 사용
        "sessions": {
            "claude_session_id": {       # key = Claude's session_id
                "created_at": "2026-03-02T12:00:00",
                "last_used": "2026-03-02T12:30:00",
                "history": ["질문1", "질문2", ...]
            }
        }
    }
}
```

---

## 4. 현재 코드 흐름

```
[사용자 메시지]
    ↓
[handlers.py] async with _user_locks[user_id]:  ← 유저별 Lock 획득
    ↓
    if no current session:
        session_id = await claude.create_session()  ← Claude session_id 획득
        sessions.create_session(user_id, session_id, message)
    ↓
[Lock 해제]
    ↓
[claude.chat(message, session_id)]  ← 명시적 session_id로 호출
    ↓
[sessions.add_message(user_id, session_id, message)]  ← 명시적 저장
```

---

## 5. 남은 개선 과제

### 5.1 CRITICAL - 파일 I/O Race Condition

**위치:** `session.py:45-48`

**문제:** `_save()` 메서드가 동기 파일 쓰기를 수행하지만, 서로 다른 유저의 동시 요청 시 동일 파일에 동시 쓰기 가능.

```python
def _save(self) -> None:
    # 파일 레벨 Lock 없음!
    with open(self.file_path, "w", encoding="utf-8") as f:
        json.dump(self._data, f, ...)
```

**권장 해결:**
```python
import threading
_file_lock = threading.Lock()

def _save(self) -> None:
    with self._file_lock:
        # atomic write 사용
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', dir=self.file_path.parent, delete=False) as tmp:
            json.dump(self._data, tmp, ...)
        os.replace(tmp.name, self.file_path)
```

### 5.2 CRITICAL - CLI 명령어 인젝션 가능성

**위치:** `client.py:115`

**문제:** 사용자 메시지가 CLI 인자로 직접 전달됨.

```python
cmd.append(message)  # '--'로 시작하는 메시지 시 의도치 않은 동작 가능
```

**권장 해결:**
```python
cmd.extend(['--', message])  # '--' 구분자로 옵션과 인자 분리
```

### 5.3 HIGH - 메모리 누수 (_user_locks)

**위치:** `handlers.py:25`

**문제:** `defaultdict(asyncio.Lock)`이 클래스 변수로 선언되어 사용자가 늘어날수록 Lock 객체 누적.

**권장 해결:**
- TTL 기반 Lock 정리 메커니즘 추가
- 또는 인스턴스 변수로 변경 + 주기적 정리

### 5.4 HIGH - SESSION_NOT_FOUND 에러 처리 불완전

**위치:** `handlers.py:370-373`

**문제:** Claude에서 `SESSION_NOT_FOUND` 반환 시 사용자에게 알림만 하고 새 세션 자동 생성 없음.

**권장 해결:**
```python
if error == "SESSION_NOT_FOUND":
    self.sessions.clear_current(user_id)
    # 새 세션으로 자동 재시도 또는 안내 메시지
```

### 5.5 HIGH - 세션 데이터 평문 저장

**위치:** `session.py:45-48`

**문제:** 대화 히스토리가 JSON 파일에 평문으로 저장됨.

**권장 해결:**
- 파일 권한 600 설정
- 민감 데이터 암호화 저장 고려

### 5.6 MEDIUM - Rate Limiting 부재

**문제:** 메시지 길이 제한(4096자)은 있으나 요청 빈도 제한 없음.

**권장 해결:**
- 사용자별 분당/시간당 요청 제한 추가

### 5.7 MEDIUM - datetime 파싱 예외 처리 없음

**위치:** `session.py:71`

```python
last_used = datetime.fromisoformat(session["last_used"])  # 예외 처리 없음
```

**권장 해결:**
```python
try:
    last_used = datetime.fromisoformat(session["last_used"])
except (ValueError, KeyError, TypeError):
    logger.warning(f"Invalid timestamp for session {session_id}")
    return None
```

### 5.8 MEDIUM - Lock 범위 내 await 호출

**위치:** `handlers.py:320-336`

**상황:** Lock 내에서 `await self.claude.create_session()` 호출 (수 초 소요).

**평가:** 의도된 설계 (race condition 방지 우선). 단, 동일 유저의 다른 메시지가 대기하게 됨.

### 5.9 LOW - 중복 코드 (인증/권한 체크)

모든 핸들러에서 동일한 패턴 반복. 데코레이터 패턴 적용 권장.

---

## 6. 검증 결과 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| Claude 세션 (`--resume`) | ✅ 정상 | - |
| chatId별 세션 저장 | ✅ 해결됨 | 유저별 Lock 적용 |
| 세션 연결 | ✅ 해결됨 | Claude session_id = Primary Key |
| Python 비동기 | ✅ 정상 | - |
| Map 세션 유실 | ✅ 해결됨 | 명시적 session_id 전달 |
| 파일 I/O 동시성 | ❌ 미해결 | Lock 또는 atomic write 필요 |
| CLI 인젝션 | ❌ 미해결 | `--` 구분자 필요 |
| 메모리 누수 | ⚠️ 주의 | Lock 정리 메커니즘 필요 |

---

## 7. 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-03-02 | 초기 분석 - Race Condition, 세션 유실 문제 발견 |
| v2.0 | 2026-03-02 | 문제 해결 후 문서 업데이트 - 새로운 개선 과제 추가 |
