# AI Bot - 프로젝트 규칙

## 개발 루틴

### 실행 스크립트 (run.sh)
```bash
./run.sh start    # 봇 시작
./run.sh stop     # 봇 중지
./run.sh restart  # 봇 재시작
./run.sh status   # 상태 확인
./run.sh log      # 로그 보기
./run.sh test     # 테스트 실행
```

### 완료 (필수 수행)
```bash
./run.sh test                             # 1. 테스트
git add -A && git commit -m "type: msg"   # 2. 커밋
git push --force origin main              # 3. 푸시
./run.sh restart                          # 4. 재시작
source venv/bin/activate && \
  python -m src.notify "변경1" -- "file1" # 5. 리포트
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

```
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

## 코드 규칙

### 구조
```
src/
├── main.py, config.py, notify.py
├── bot/     # 텔레그램 (handlers, middleware, formatters)
└── claude/  # AI CLI (client, session)
```

### 네이밍
- 파일: `snake_case.py`
- 클래스: `PascalCase`
- 함수/변수: `snake_case`
- 상수: `UPPER_SNAKE_CASE`

### 비동기
- I/O → `async/await`
- subprocess → `asyncio.create_subprocess_exec`

### 테스트 코드
- 모듈: 테스트 의도 설명 (docstring)
- 메서드: 간단한 설명 (docstring)

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TELEGRAM_TOKEN` | (필수) | 봇 토큰 |
| `ALLOWED_CHAT_IDS` | (빈값) | 허용 채팅 ID (쉼표 구분) |
| `MAINTAINER_CHAT_ID` | (빈값) | 개발 리포트 수신 |
| `AI_COMMAND` | `claude` | AI CLI 명령어 |
| `SESSION_TIMEOUT_HOURS` | `24` | 세션 만료 시간 |
| `REQUIRE_AUTH` | `true` | 인증 필요 여부 |
| `AUTH_SECRET_KEY` | (조건부 필수) | 인증 키 (`REQUIRE_AUTH=true` 시 필수) |
| `AUTH_TIMEOUT_MINUTES` | `30` | 인증 유효 시간 |
## 플러그인 아키텍처

### 디렉토리 구조
```
telegram-claude-bot/
├── src/
│   └── plugins/
│       └── loader.py          # 플러그인 로더
└── plugins/
    ├── default/               # Git 관리 ✅ (기본 제공)
    │   └── example.py
    └── custom/                # Git 무시 ❌ (개인용)
        └── my_plugin.py
```

### 플러그인 규칙 (CRITICAL)

1. **안전한 로딩**: 플러그인 로드 실패 시 봇은 계속 동작
   - 각 플러그인은 try-catch로 격리
   - 실패한 플러그인만 스킵, 나머지 정상 로드
   - 에러 로그로 알림

2. **검증 후 배포**: Claude가 custom에 코드 작성 시
   - 반드시 문법 검증 (`python -m py_compile`)
   - 검증 실패해도 기존 봇은 정상 동작 보장
   - 실패 시 사용자에게 알림

3. **핫 리로드**: 봇 재시작 없이 플러그인 갱신 가능

## 금지

- `.env` 커밋 금지
- `.data/` 커밋 금지
- 토큰 하드코딩 금지
