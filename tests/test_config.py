from pathlib import Path

import pytest

from msclaw.config import ConfigurationError, Settings


def test_settings_from_env(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "telegram-test-token",
            "OWNER_ID": "123",
            "ANTHROPIC_API_KEY": "anthropic-test-key",
            "ASSISTANT_NAME": "Test Bot",
        },
        project_dir=tmp_path,
    )

    assert settings.owner_id == 123
    assert settings.assistant_name == "Test Bot"
    assert settings.workspace_dir == (tmp_path / "workspace").resolve()
    assert settings.agent_env() == {"ANTHROPIC_API_KEY": "anthropic-test-key"}


@pytest.mark.parametrize("owner_id", ["not-a-number", "0", "-1"])
def test_settings_reject_invalid_owner(owner_id: str, tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "OWNER_ID": owner_id,
                "ANTHROPIC_API_KEY": "key",
            },
            project_dir=tmp_path,
        )


def test_settings_report_missing_variables(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="TELEGRAM_BOT_TOKEN.*ANTHROPIC_API_KEY"):
        Settings.from_env({"OWNER_ID": "123"}, project_dir=tmp_path)
