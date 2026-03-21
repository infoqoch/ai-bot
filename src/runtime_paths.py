"""Runtime filesystem paths for bot process artifacts."""

from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    """Return the repository root for relative runtime paths."""
    return _PROJECT_ROOT


def _resolve_path(raw: str | None, default: Path) -> Path:
    if not raw:
        return default

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project_root() / path
    return path


def get_data_dir() -> Path:
    """Return the directory used for runtime artifacts."""
    return _resolve_path(os.getenv("BOT_DATA_DIR"), project_root() / ".data")


def get_log_dir() -> Path:
    """Return the directory used for application logs."""
    return _resolve_path(os.getenv("BOT_LOG_DIR"), get_data_dir() / "logs")


def get_main_lock_path() -> Path:
    """Return the singleton lock path for the main bot process."""
    return _resolve_path(os.getenv("BOT_LOCK_FILE"), get_data_dir() / "telegram-bot.lock")


def get_supervisor_lock_path() -> Path:
    """Return the singleton lock path for the supervisor process."""
    return _resolve_path(
        os.getenv("BOT_SUPERVISOR_LOCK_FILE"),
        get_data_dir() / "telegram-bot-supervisor.lock",
    )

