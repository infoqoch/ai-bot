# Development Rules

## 개발 워크플로우

### 1. 개발 시작
```bash
source venv/bin/activate
python -m src.main  # 봇 실행
```

### 2. 개발 완료 시
개발이 완료되면 다음을 수행:
1. 테스트 실행: `pytest`
2. 커밋 및 푸시
3. `MAINTAINER_CHAT_ID`로 개발 요약 전송

### 3. 커밋 컨벤션
```
feat: 새 기능
fix: 버그 수정
refactor: 리팩토링
docs: 문서
test: 테스트
chore: 기타
```

## 코드 규칙

### 구조
- `src/bot/` - 텔레그램 관련
- `src/claude/` - AI CLI 관련
- `tests/` - 테스트

### 네이밍
- 파일: `snake_case.py`
- 클래스: `PascalCase`
- 함수/변수: `snake_case`
- 상수: `UPPER_SNAKE_CASE`

### 타입 힌트
```python
def function(param: str) -> dict:
    ...
```

### 비동기
- I/O 작업은 `async/await` 사용
- `subprocess` → `asyncio.create_subprocess_exec`

## 개발 완료 리포트

개발 완료 시 `MAINTAINER_CHAT_ID`로 다음 형식 전송:

```
🔧 개발 완료 리포트

📝 변경사항:
• [변경 내용 1]
• [변경 내용 2]

📁 수정된 파일:
• src/...
• tests/...

✅ 테스트: 통과
🚀 상태: 배포 완료
```
