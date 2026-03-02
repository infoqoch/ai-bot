# AI Bot - Project Rules

이 프로젝트에서 Claude와 협업 시 따르는 규칙입니다.

## 개발 루틴

### 1. 개발 시작
```bash
# 봇 상태 확인
ps aux | grep "src.main" | grep -v grep

# 봇 실행 (필요 시)
source venv/bin/activate && nohup python -m src.main > /tmp/telegram-bot.log 2>&1 &
```

### 2. 개발 중
- 변경사항은 즉시 적용
- 테스트 필요 시: `pytest`
- 로그 확인: `tail -f /tmp/telegram-bot.log`

### 3. 개발 완료 시 (필수)
다음 순서를 **반드시** 수행:

```bash
# 1. 테스트
pytest

# 2. 커밋 (conventional commits)
git add -A
git commit -m "type: description

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# 3. 푸시 (force)
git push --force origin main

# 4. 봇 재시작
pkill -9 -f "src.main"; sleep 1
source venv/bin/activate && nohup python -m src.main > /tmp/telegram-bot.log 2>&1 &

# 5. 개발 리포트 전송
python -m src.notify "변경1" "변경2" -- "file1.py" "file2.py"
```

## 커밋 컨벤션

| Type | 용도 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `refactor` | 리팩토링 |
| `docs` | 문서 |
| `test` | 테스트 |
| `chore` | 기타 |

## 코드 규칙

### 구조
```
src/
├── main.py         # 엔트리포인트
├── config.py       # 설정 (Pydantic)
├── notify.py       # 개발 알림
├── bot/            # 텔레그램 관련
│   ├── handlers.py
│   ├── middleware.py
│   └── formatters.py
└── claude/         # AI CLI 관련
    ├── client.py
    └── session.py
```

### 네이밍
- 파일: `snake_case.py`
- 클래스: `PascalCase`
- 함수/변수: `snake_case`
- 상수: `UPPER_SNAKE_CASE`

### 비동기
- I/O 작업은 `async/await` 사용
- subprocess → `asyncio.create_subprocess_exec`

### 타입 힌트
```python
def function(param: str) -> dict:
    ...
```

## 설정 파일

| 파일 | 용도 | Git |
|------|------|-----|
| `.env` | 시크릿 | ❌ |
| `.env.example` | 템플릿 | ✅ |
| `.data/` | 런타임 데이터 | ❌ |

## 주요 환경변수

| 변수 | 설명 |
|------|------|
| `TELEGRAM_TOKEN` | 봇 토큰 |
| `ALLOWED_CHAT_IDS` | 허용 채팅 ID |
| `MAINTAINER_CHAT_ID` | 개발 리포트 수신 |
| `AI_COMMAND` | AI CLI 명령어 |
| `REQUIRE_AUTH` | 인증 필요 여부 |

## 금지 사항

- `.env` 파일 커밋 금지
- `data/sessions.json` 커밋 금지
- 토큰/시크릿 하드코딩 금지
