# Todo 플러그인 기획서

## 개요

스케줄 기반 할일 관리 플러그인. 시간대별(오전/오후/저녁) 리마인더를 통해 사용자의 일일 할일을 관리.

## 시간대 정의

| 시간대 | 시간 범위 | 리마인더 |
|--------|----------|----------|
| 오전 | 08:00 ~ 12:00 | 10:00 체크 |
| 오후 | 12:00 ~ 18:00 | 15:00 체크 |
| 저녁 | 18:00 ~ 24:00 | 19:00 체크 |

## 스케줄 동작

### 08:00 - 아침 질문
```
🌅 좋은 아침이에요!

오늘 할 일이 뭐예요?
편하게 말해주세요. 시간대별로 정리해드릴게요.

예: 오전에 회의하고, 점심에 친구 만나고, 저녁엔 운동해야해
```
- `pending_input` 상태 활성화
- 사용자의 다음 메시지를 할일로 파싱

### 10:00, 15:00, 19:00 - 시간대별 체크
```
🌅 오전 할일 어때요?

⬜ 1. 회의
⬜ 2. 보고서 작성

완료한 건 말해주세요!
예: 회의 끝났어, 1번 완료
```
- 해당 시간대에 등록된 할일이 있을 때만 전송
- 모두 완료면 "👏 모두 완료!" 메시지

## 사용자 명령어

### 조회
- "할일 보여줘", "오늘 할일", "todo"
- "오전 할일", "오후 할일", "저녁 할일"

### 추가
- "할일 추가: 회의하기"
- "오전에 회의 추가해줘"
- "저녁에 운동 넣어줘"

### 완료
- "회의 끝났어", "1번 완료"
- "오전 1번 done"

### 삭제
- "회의 삭제", "2번 지워"
- "오후 3번 제거"

## 데이터 구조

```json
{
  "date": "2026-03-04",
  "tasks": {
    "morning": [
      {"text": "회의", "done": false, "created_at": "...", "completed_at": null}
    ],
    "afternoon": [],
    "evening": []
  },
  "pending_input": false,
  "pending_input_timestamp": null,
  "last_reminder": null
}
```

저장 위치: `.data/todo/{chat_id}.json`

## 현재 문제점 (2026-03-04)

### 1. 스케줄러 시간대 미지정
`scheduler.py`의 `run_daily()` 호출 시 `tzinfo=KST`가 누락됨.

**현재 코드:**
```python
job = job_queue.run_daily(
    self._morning_ask_callback,
    time=SCHEDULE_TIMES["morning_ask"],  # time(8, 0) - tzinfo 없음
    name="todo_morning_ask",
)
```

**수정 필요:**
```python
job = job_queue.run_daily(
    self._morning_ask_callback,
    time=time(8, 0, tzinfo=KST),  # KST 명시
    name="todo_morning_ask",
)
```

### 2. SCHEDULE_TIMES에 tzinfo 누락
```python
# 현재 (잘못됨)
SCHEDULE_TIMES = {
    "morning_ask": time(8, 0),
    ...
}

# 수정 필요
SCHEDULE_TIMES = {
    "morning_ask": time(8, 0, tzinfo=KST),
    ...
}
```

### 3. 플러그인 비활성화 기능 없음
- HourlyPing처럼 플러그인을 삭제하지 않고 비활성화하는 기능 필요
- `.env` 또는 설정 파일로 on/off 제어

## 구현 우선순위

1. **[CRITICAL]** 스케줄러 시간대(KST) 수정
2. **[HIGH]** 플러그인 비활성화 기능 추가
3. **[MEDIUM]** 테스트 명령어 추가 (`/todo_test` - 즉시 리마인더)
