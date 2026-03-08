"""Tests for shared runtime exit code semantics."""

from src.runtime_exit_codes import RuntimeExitCode, describe_exit_code, is_restartable_exit_code


def test_non_restartable_exit_codes():
    assert is_restartable_exit_code(int(RuntimeExitCode.OK)) is False
    assert is_restartable_exit_code(int(RuntimeExitCode.CONFIG_ERROR)) is False
    assert is_restartable_exit_code(int(RuntimeExitCode.LOCK_HELD)) is False


def test_unknown_nonzero_exit_code_is_restartable():
    assert is_restartable_exit_code(1) is True


def test_describe_exit_code_labels_known_values():
    assert describe_exit_code(int(RuntimeExitCode.CONFIG_ERROR)) == "startup configuration error"
    assert describe_exit_code(int(RuntimeExitCode.LOCK_HELD)) == "main process lock unavailable"
