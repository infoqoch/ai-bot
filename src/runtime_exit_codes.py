"""Shared process exit codes for the bot runtime lifecycle."""

from __future__ import annotations

from enum import IntEnum


class RuntimeExitCode(IntEnum):
    """Process exit codes understood by both main and supervisor."""

    OK = 0
    CONFIG_ERROR = 78
    LOCK_HELD = 79


_DESCRIPTIONS = {
    RuntimeExitCode.OK: "normal shutdown",
    RuntimeExitCode.CONFIG_ERROR: "startup configuration error",
    RuntimeExitCode.LOCK_HELD: "main process lock unavailable",
}


def is_restartable_exit_code(exit_code: int) -> bool:
    """Return whether supervisor should retry after one child exit."""
    try:
        code = RuntimeExitCode(exit_code)
    except ValueError:
        return exit_code != int(RuntimeExitCode.OK)

    return code not in {
        RuntimeExitCode.OK,
        RuntimeExitCode.CONFIG_ERROR,
        RuntimeExitCode.LOCK_HELD,
    }


def describe_exit_code(exit_code: int) -> str:
    """Return one operator-facing label for an exit code."""
    try:
        code = RuntimeExitCode(exit_code)
    except ValueError:
        return f"exit_code={exit_code}"

    return _DESCRIPTIONS.get(code, f"exit_code={int(code)}")
