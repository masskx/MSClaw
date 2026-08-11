from pathlib import Path

from claude_agent_sdk import ProcessError, ResultMessage

from msclaw.agent import ALLOWED_TOOLS, AgentService
from msclaw.config import Settings
from msclaw.storage import FileStorage


def test_builtin_tool_names_match_sdk_conventions() -> None:
    assert {"Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Bash"} <= set(
        ALLOWED_TOOLS
    )
    assert not {"read", "write", "bash"} & set(ALLOWED_TOOLS)


def make_service(tmp_path: Path) -> tuple[AgentService, FileStorage, Settings]:
    settings = Settings(
        telegram_bot_token="token",
        owner_id=1,
        anthropic_api_key="key",
        anthropic_base_url=None,
        assistant_name="Test Bot",
        workspace_dir=tmp_path / "workspace",
        data_dir=tmp_path / "data",
    )
    storage = FileStorage(settings.data_dir, settings.workspace_dir, settings.assistant_name)
    storage.ensure_workspace()
    return AgentService(settings, storage), storage, settings


def result_message(session_id: str, text: str) -> ResultMessage:
    return ResultMessage(
        subtype="result",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id=session_id,
        result=text,
    )


async def test_stale_session_falls_back_to_fresh(tmp_path: Path) -> None:
    service, storage, _ = make_service(tmp_path)
    storage.save_session_id("stale-session")
    attempts: list[str | None] = []

    async def flaky_runner(prompt, options):
        attempts.append(options.resume)
        if len(attempts) == 1:
            raise ProcessError("Command failed with exit code 1")
        yield result_message("new-session", "hello")

    service._query_runner = flaky_runner
    result = await service.run("hi", bot=None, chat_id=1)
    assert result == "hello"
    assert attempts == ["stale-session", None]
    assert storage.load_session_id() == "new-session"


async def test_resume_flag_set_when_session_exists(tmp_path: Path) -> None:
    service, storage, _ = make_service(tmp_path)
    storage.save_session_id("existing-session")
    seen: list[str | None] = []

    async def capturing_runner(prompt, options):
        seen.append(options.resume)
        yield result_message("existing-session", "ok")

    service._query_runner = capturing_runner
    result = await service.run("hi", bot=None, chat_id=1)
    assert result == "ok"
    assert seen == ["existing-session"]
