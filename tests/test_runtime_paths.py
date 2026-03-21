"""Tests for runtime filesystem path helpers."""

from __future__ import annotations

from src import runtime_paths


def test_data_dir_defaults_to_project_data(monkeypatch):
    monkeypatch.delenv("BOT_DATA_DIR", raising=False)

    assert runtime_paths.get_data_dir() == runtime_paths.project_root() / ".data"


def test_data_dir_relative_override_uses_project_root(monkeypatch):
    monkeypatch.setenv("BOT_DATA_DIR", "var/runtime")

    assert runtime_paths.get_data_dir() == runtime_paths.project_root() / "var/runtime"


def test_log_dir_defaults_under_data_dir(monkeypatch):
    monkeypatch.delenv("BOT_LOG_DIR", raising=False)
    monkeypatch.setenv("BOT_DATA_DIR", "var/runtime")

    assert runtime_paths.get_log_dir() == runtime_paths.project_root() / "var/runtime" / "logs"


def test_lock_paths_follow_data_dir(monkeypatch):
    monkeypatch.setenv("BOT_DATA_DIR", "var/runtime")
    monkeypatch.delenv("BOT_LOCK_FILE", raising=False)
    monkeypatch.delenv("BOT_SUPERVISOR_LOCK_FILE", raising=False)

    assert runtime_paths.get_main_lock_path() == runtime_paths.project_root() / "var/runtime" / "telegram-bot.lock"
    assert runtime_paths.get_supervisor_lock_path() == runtime_paths.project_root() / "var/runtime" / "telegram-bot-supervisor.lock"
