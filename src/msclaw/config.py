"""Application configuration with fail-fast validation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    owner_id: int
    anthropic_api_key: str
    anthropic_base_url: str | None
    assistant_name: str
    workspace_dir: Path
    data_dir: Path

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        project_dir: Path | None = None,
    ) -> Settings:
        env = os.environ if environ is None else environ
        root = (project_dir or Path.cwd()).resolve()

        missing = [
            name
            for name in ("TELEGRAM_BOT_TOKEN", "OWNER_ID", "ANTHROPIC_API_KEY")
            if not env.get(name, "").strip()
        ]
        if missing:
            raise ConfigurationError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        try:
            owner_id = int(env["OWNER_ID"])
        except ValueError as exc:
            raise ConfigurationError("OWNER_ID must be an integer") from exc
        if owner_id <= 0:
            raise ConfigurationError("OWNER_ID must be a positive integer")

        workspace_dir = Path(env.get("MSCLAW_WORKSPACE", root / "workspace")).resolve()
        data_dir = Path(env.get("MSCLAW_DATA_DIR", root / "data")).resolve()
        return cls(
            telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
            owner_id=owner_id,
            anthropic_api_key=env["ANTHROPIC_API_KEY"],
            anthropic_base_url=env.get("ANTHROPIC_BASE_URL") or None,
            assistant_name=env.get("ASSISTANT_NAME", "Memory Bot"),
            workspace_dir=workspace_dir,
            data_dir=data_dir,
        )

    def agent_env(self) -> dict[str, str]:
        values = {"ANTHROPIC_API_KEY": self.anthropic_api_key}
        if self.anthropic_base_url:
            values["ANTHROPIC_BASE_URL"] = self.anthropic_base_url
        return values
