# TODO - Telegram Claude Bot

## 완료된 작업 ✅

### Fire-and-Forget 패턴 (2026-03-02)
- [x] 핸들러 즉시 리턴, 백그라운드에서 Claude 호출
- [x] Race Condition 방지 (유저별 Lock)
- [x] 명시적 파라미터 전달 (chat_id, bot, session_id)
- [x] 포괄적 예외 처리

### 리소스 관리 (2026-03-02)
- [x] Semaphore: 유저당 동시 3개 요청 제한
- [x] Watchdog: 30분 초과 태스크 자동 정리
- [x] 태스크 추적 (`_active_tasks`)
- [x] 좀비 프로세스 kill (`_kill_claude_process`)

---

## 남은 작업

### 낮음 - Graceful Shutdown
> 봇 종료 시 진행 중인 Claude 호출이 즉시 취소됨

**현재 영향**: 낮음 (재시작 빈도 낮음)

**구현 방안**:
```python
# Application shutdown hook에서 대기
async def shutdown(self):
    if self._active_tasks:
        await asyncio.gather(*[info.task for info in self._active_tasks.values()], return_exceptions=True)
```

**언제 필요한가?**
- 자주 재시작하는 환경
- 프로덕션 배포 시

---

## 참고

- Fire-and-Forget 분석: 안정성 점수 8/10 → 10/10 (Semaphore+Watchdog 적용 후)
- 테스트 커버리지: 100개 테스트 통과
