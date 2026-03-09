"""Static guardrails that keep plugin logic out of core runtime paths."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIRS = [
    PROJECT_ROOT / "plugins" / "builtin",
    PROJECT_ROOT / "plugins" / "custom",
]
CORE_ENTRYPOINTS = [
    PROJECT_ROOT / "src" / "bot" / "handlers" / "message_handlers.py",
    PROJECT_ROOT / "src" / "bot" / "handlers" / "callback_handlers.py",
    PROJECT_ROOT / "src" / "main.py",
]
PLUGIN_NAME_PATTERN = re.compile(r"\b(todo|memo|weather|hourly_ping)\b")
LEGACY_REPOSITORY_CALLS = [
    "add_memo(",
    "get_memo(",
    "delete_memo(",
    "list_memos(",
    "clear_memos(",
    "add_todo(",
    "get_todo(",
    "toggle_todo(",
    "delete_todo(",
    "list_todos_by_date(",
    "clear_todos_by_date(",
    "mark_todo_done(",
    "get_pending_todos(",
    "move_todos_to_date(",
    "get_todos_by_date_range(",
    "get_todo_stats(",
    "set_weather_location(",
    "get_weather_location(",
    "delete_weather_location(",
]


def _iter_python_files(base_dir: Path) -> list[Path]:
    return sorted(path for path in base_dir.rglob("*.py") if "__pycache__" not in path.parts)


def test_plugin_sources_do_not_access_core_repository_objects_directly():
    offenders: list[str] = []

    for base_dir in PLUGIN_DIRS:
        for path in _iter_python_files(base_dir):
            text = path.read_text()
            if "self.repository" in text or "._conn" in text or "_repository" in text:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert not offenders, f"Plugin source must use bounded adapters only: {offenders}"


def test_plugin_loader_does_not_touch_repository_connection_directly():
    loader_source = (PROJECT_ROOT / "src" / "plugins" / "loader.py").read_text()
    assert "_conn" not in loader_source


def test_core_entrypoints_do_not_hardcode_plugin_names():
    offenders: list[str] = []

    for path in CORE_ENTRYPOINTS:
        text = path.read_text()
        if PLUGIN_NAME_PATTERN.search(text):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert not offenders, f"Core runtime paths should not hardcode plugin names: {offenders}"


def test_plugin_storage_adapter_avoids_legacy_repository_plugin_methods():
    adapter_source = (
        PROJECT_ROOT / "src" / "repository" / "adapters" / "plugin_storage.py"
    ).read_text()

    offenders = [
        call for call in LEGACY_REPOSITORY_CALLS
        if f"._repo.{call}" in adapter_source
    ]
    assert not offenders, f"Plugin storage adapter must not rely on legacy repository shims: {offenders}"
