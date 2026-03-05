"""ProcessLock 테스트 - flock 기반 프로세스 싱글톤 락."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import fcntl

import pytest

from src.lock import ProcessLock


class TestProcessLock:
    """ProcessLock 기본 기능 테스트."""

    def test_acquire_success(self, tmp_path):
        """락 획득 성공."""
        lock_file = tmp_path / "test.lock"
        lock = ProcessLock(lock_file)

        assert lock.acquire() is True
        assert lock_file.exists()
        assert lock.get_owner_pid() == os.getpid()

        lock.release()

    def test_acquire_writes_pid(self, tmp_path):
        """락 획득 시 PID가 파일에 기록됨."""
        lock_file = tmp_path / "test.lock"
        lock = ProcessLock(lock_file)

        lock.acquire()
        content = lock_file.read_text().strip()
        assert content == str(os.getpid())

        lock.release()

    def test_release_does_not_delete_file(self, tmp_path):
        """락 해제 시 파일은 삭제되지 않음 (race condition 방지)."""
        lock_file = tmp_path / "test.lock"
        lock = ProcessLock(lock_file)

        lock.acquire()
        lock.release()

        # 파일은 여전히 존재해야 함
        assert lock_file.exists()

    def test_acquire_fails_when_locked(self, tmp_path):
        """이미 락이 걸려있으면 획득 실패."""
        lock_file = tmp_path / "test.lock"
        lock1 = ProcessLock(lock_file)
        lock2 = ProcessLock(lock_file)

        assert lock1.acquire() is True
        assert lock2.acquire() is False  # 두 번째는 실패

        lock1.release()

    def test_acquire_after_release(self, tmp_path):
        """락 해제 후 다시 획득 가능."""
        lock_file = tmp_path / "test.lock"
        lock1 = ProcessLock(lock_file)
        lock2 = ProcessLock(lock_file)

        lock1.acquire()
        lock1.release()

        # 해제 후 다른 인스턴스가 획득 가능
        assert lock2.acquire() is True
        lock2.release()

    def test_release_without_acquire(self, tmp_path):
        """획득하지 않은 락 해제는 안전하게 무시됨."""
        lock_file = tmp_path / "test.lock"
        lock = ProcessLock(lock_file)

        # 예외 없이 실행되어야 함
        lock.release()

    def test_double_release(self, tmp_path):
        """두 번 해제해도 안전."""
        lock_file = tmp_path / "test.lock"
        lock = ProcessLock(lock_file)

        lock.acquire()
        lock.release()
        lock.release()  # 두 번째 해제도 안전


class TestGetOwnerPid:
    """get_owner_pid 메서드 테스트."""

    def test_get_owner_pid_no_file(self, tmp_path):
        """락 파일이 없으면 None."""
        lock_file = tmp_path / "nonexistent.lock"
        lock = ProcessLock(lock_file)

        assert lock.get_owner_pid() is None

    def test_get_owner_pid_invalid_content(self, tmp_path):
        """락 파일 내용이 유효하지 않으면 None."""
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("not-a-number")
        lock = ProcessLock(lock_file)

        assert lock.get_owner_pid() is None

    def test_get_owner_pid_empty_file(self, tmp_path):
        """빈 락 파일은 None."""
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("")
        lock = ProcessLock(lock_file)

        assert lock.get_owner_pid() is None

    def test_get_owner_pid_valid(self, tmp_path):
        """유효한 PID 반환."""
        lock_file = tmp_path / "test.lock"
        lock_file.write_text("12345")
        lock = ProcessLock(lock_file)

        assert lock.get_owner_pid() == 12345


class TestIsLocked:
    """is_locked 메서드 테스트."""

    def test_is_locked_no_file(self, tmp_path):
        """락 파일이 없으면 False."""
        lock_file = tmp_path / "nonexistent.lock"
        lock = ProcessLock(lock_file)

        assert lock.is_locked() is False

    def test_is_locked_when_locked(self, tmp_path):
        """락이 걸려있으면 True."""
        lock_file = tmp_path / "test.lock"
        lock1 = ProcessLock(lock_file)
        lock2 = ProcessLock(lock_file)

        lock1.acquire()
        assert lock2.is_locked() is True

        lock1.release()

    def test_is_locked_after_release(self, tmp_path):
        """락 해제 후 False."""
        lock_file = tmp_path / "test.lock"
        lock1 = ProcessLock(lock_file)
        lock2 = ProcessLock(lock_file)

        lock1.acquire()
        lock1.release()

        assert lock2.is_locked() is False


class TestErrorHandling:
    """에러 처리 테스트."""

    def test_acquire_io_error(self, tmp_path):
        """파일 열기 실패 시 False 반환."""
        lock_file = tmp_path / "readonly" / "test.lock"
        # 부모 디렉토리가 없어서 실패
        lock = ProcessLock(lock_file)

        assert lock.acquire() is False

    def test_acquire_flock_error(self, tmp_path):
        """flock 실패 시 False 반환 및 fd 정리."""
        lock_file = tmp_path / "test.lock"
        lock = ProcessLock(lock_file)

        with patch('fcntl.flock', side_effect=IOError("flock failed")):
            assert lock.acquire() is False
            assert lock._fd is None  # fd가 정리되었는지 확인

    def test_release_exception_handling(self, tmp_path):
        """해제 시 예외가 발생해도 안전하게 처리."""
        lock_file = tmp_path / "test.lock"
        lock = ProcessLock(lock_file)
        lock.acquire()

        # flock 해제 시 예외 발생해도 안전해야 함
        with patch('fcntl.flock', side_effect=Exception("unlock failed")):
            lock.release()  # 예외 없이 실행되어야 함

        assert lock._fd is None


class TestConcurrency:
    """동시성 관련 테스트."""

    def test_flock_is_exclusive(self, tmp_path):
        """flock이 배타적 락을 제공하는지 확인."""
        lock_file = tmp_path / "test.lock"

        # 첫 번째 프로세스가 락 획득
        fd1 = open(lock_file, "w")
        fcntl.flock(fd1.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd1.write("1")
        fd1.flush()

        # 두 번째 시도는 실패해야 함
        fd2 = open(lock_file, "w")
        with pytest.raises(BlockingIOError):
            fcntl.flock(fd2.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        fd2.close()
        fcntl.flock(fd1.fileno(), fcntl.LOCK_UN)
        fd1.close()

    def test_kernel_releases_lock_on_close(self, tmp_path):
        """fd를 닫으면 커널이 락을 해제하는지 확인."""
        lock_file = tmp_path / "test.lock"

        # 첫 번째 프로세스가 락 획득 후 fd 닫기
        fd1 = open(lock_file, "w")
        fcntl.flock(fd1.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd1.close()  # 명시적 LOCK_UN 없이 닫기

        # 두 번째 시도는 성공해야 함 (커널이 락 해제)
        fd2 = open(lock_file, "w")
        fcntl.flock(fd2.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # 성공!
        fd2.close()
