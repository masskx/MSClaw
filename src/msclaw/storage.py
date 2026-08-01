"""Local session state and Markdown conversation archive."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class FileStorage:
    data_dir: Path
    workspace_dir: Path
    assistant_name: str

    @property
    def state_file(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def conversations_dir(self) -> Path:
        return self.workspace_dir / "conversations"

    def ensure_workspace(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        memory_file = self.workspace_dir / "CLAUDE.md"
        if not memory_file.exists():
            memory_file.write_text(self._memory_template(), encoding="utf-8")

    def load_session_id(self) -> str | None:
        if not self.state_file.exists():
            return None
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot read session state: {self.state_file}") from exc
        session_id = payload.get("session_id")
        return session_id if isinstance(session_id, str) and session_id else None

    def save_session_id(self, session_id: str) -> None:
        if not session_id:
            raise ValueError("session_id must not be empty")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"session_id": session_id}, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temporary, self.state_file)

    def clear_session_id(self) -> bool:
        try:
            self.state_file.unlink()
        except FileNotFoundError:
            return False
        return True

    def archive_conversation(
        self,
        user_message: str,
        assistant_response: str,
        *,
        now: datetime | None = None,
    ) -> Path:
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        timestamp = now or datetime.now(UTC)
        timestamp = timestamp.astimezone(UTC)
        day = timestamp.strftime("%Y-%m-%d")
        path = self.conversations_dir / f"{day}.md"
        heading = "" if path.exists() else f"# Conversation log - {day}\n\n"
        entry = (
            f"## {timestamp.strftime('%H:%M:%S UTC')}\n\n"
            f"**User**: {user_message}\n\n"
            f"**{self.assistant_name}**: {assistant_response}\n\n---\n\n"
        )
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(heading + entry)
        return path

    def _memory_template(self) -> str:
        return f"""# {self.assistant_name} - Personal AI assistant

You are {self.assistant_name}, a personal AI assistant running on Telegram.

## Capabilities

- Read and edit files inside this workspace.
- Search the web when the configured Claude tools support it.
- Send progress messages through the Telegram MCP tool.

## Long-term memory

- This file is long-term memory. Update it only with durable, useful information.
- `conversations/` contains daily Markdown archives.
- Use file search to retrieve relevant prior conversations.
"""
