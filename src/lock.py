"""프로세스 싱글톤 락 - flock 기반.

사용법:
    lock = ProcessLock(Path("/tmp/my-app.lock"))
    if not lock.acquire():
        print("이미 실행 중")
        sys.exit(1)
    atexit.register(lock.release)
    # ... 앱 실행 ...
"""

import fcntl
import os
from pathlib import Path


class ProcessLock:
    """flock 기반 프로세스 싱글톤 락.

    특징:
    - flock(LOCK_EX | LOCK_NB)로 원자적 배타 락
    - 프로세스 종료 시 커널이 자동 해제
    - 파일 삭제 안 함 (race condition 방지)
    """

    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self._fd = None

    def acquire(self) -> bool:
        """락 획득. 성공 시 True, 이미 잠겨있으면 False.

        flock이 원자적 배타 락을 보장하므로 동시 실행 시
        정확히 하나만 성공합니다.
        """
        try:
            self._fd = open(self.lock_file, "w")
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fd.write(str(os.getpid()))
            self._fd.flush()
            return True
        except (IOError, OSError):
            if self._fd:
                self._fd.close()
                self._fd = None
            return False

    def release(self):
        """락 해제. 파일은 삭제하지 않음 (race condition 방지)."""
        if self._fd:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
            except Exception:
                pass
            self._fd = None

    def get_owner_pid(self) -> int | None:
        """락 파일에 기록된 PID 반환. 없으면 None."""
        try:
            if self.lock_file.exists():
                return int(self.lock_file.read_text().strip())
        except (ValueError, IOError):
            pass
        return None

    def is_locked(self) -> bool:
        """락이 걸려있는지 확인 (비파괴적 테스트)."""
        if not self.lock_file.exists():
            return False

        try:
            fd = open(self.lock_file, "r")
            try:
                # 논블로킹으로 공유 락 시도 (읽기만)
                fcntl.flock(fd.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
                return False  # 락 획득 성공 = 아무도 안 잡고 있음
            except (IOError, OSError):
                return True  # 락 획득 실패 = 누가 잡고 있음
            finally:
                fd.close()
        except (IOError, OSError):
            return False
