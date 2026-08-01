from datetime import UTC, datetime
from pathlib import Path

import pytest

from msclaw.storage import FileStorage


@pytest.fixture
def storage(tmp_path: Path) -> FileStorage:
    return FileStorage(tmp_path / "data", tmp_path / "workspace", "Test Bot")


def test_session_round_trip_and_clear(storage: FileStorage) -> None:
    assert storage.load_session_id() is None
    storage.save_session_id("session-1")
    assert storage.load_session_id() == "session-1"
    assert storage.clear_session_id() is True
    assert storage.clear_session_id() is False


def test_corrupt_session_state_has_actionable_error(storage: FileStorage) -> None:
    storage.data_dir.mkdir(parents=True)
    storage.state_file.write_text("not-json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Cannot read session state"):
        storage.load_session_id()


def test_archive_appends_to_daily_markdown(storage: FileStorage) -> None:
    timestamp = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)
    path = storage.archive_conversation("hello", "world", now=timestamp)
    storage.archive_conversation("again", "done", now=timestamp)
    content = path.read_text(encoding="utf-8")
    assert content.count("# Conversation log - 2026-08-01") == 1
    assert "**User**: hello" in content
    assert "**Test Bot**: done" in content


def test_ensure_workspace_preserves_existing_memory(storage: FileStorage) -> None:
    storage.workspace_dir.mkdir(parents=True)
    memory = storage.workspace_dir / "CLAUDE.md"
    memory.write_text("custom memory", encoding="utf-8")
    storage.ensure_workspace()
    assert memory.read_text(encoding="utf-8") == "custom memory"
