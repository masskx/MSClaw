"""Claude Agent SDK integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    PermissionResultAllow,
    ProcessError,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from .config import Settings
from .storage import FileStorage

LOGGER = logging.getLogger(__name__)

ALLOWED_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "Bash",
    "mcp__assistant__send_message",
]


class AgentError(RuntimeError):
    """Raised when the Claude agent cannot return a final response."""


class AgentService:
    def __init__(
        self,
        settings: Settings,
        storage: FileStorage,
        *,
        query_runner: Callable[..., AsyncIterator[Any]] = query,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self._query_runner = query_runner
        self._lock = asyncio.Lock()

    async def run(self, prompt: str, bot: Any, chat_id: int) -> str:
        if not prompt.strip(): # 先校验消息为空的情况，然后抛异常
            raise ValueError("prompt must not be empty")
        async with self._lock:
            return await self._run(prompt, bot, chat_id) # 不为空调用模型

    async def _run(self, prompt: str, bot: Any, chat_id: int) -> str:
        options = self._build_options(bot, chat_id)
        session_id = self.storage.load_session_id()
        if session_id:
            options.resume = session_id
        try:
            return await self._query(prompt, options)
        except ProcessError:
            # The stored session no longer exists locally (e.g. ~/.claude was
            # cleaned or the session belongs to another working directory), so
            # the CLI refuses to resume. Fall back to a fresh conversation.
            LOGGER.warning(
                "Resuming session %s failed, falling back to a new session", session_id
            )
            self.storage.clear_session_id()
            return await self._query(prompt, self._build_options(bot, chat_id))

    async def _query(self, prompt: str, options: ClaudeAgentOptions) -> str:
        async for message in self._query_runner(prompt=self._prompt(prompt), options=options):
            if isinstance(message, ResultMessage):
                if message.session_id:
                    self.storage.save_session_id(message.session_id)
                if message.result:
                    return message.result
        raise AgentError("Claude agent completed without a final response")

    def _build_options(self, bot: Any, chat_id: int) -> ClaudeAgentOptions:
        async def allow_configured_tools(*_: Any) -> PermissionResultAllow:
            return PermissionResultAllow(behavior="allow")

        return ClaudeAgentOptions(
            cwd=str(self.settings.workspace_dir),
            can_use_tool=allow_configured_tools,
            allowed_tools=ALLOWED_TOOLS,
            agents={
                "coder": AgentDefinition(
                    description="Python development specialist",
                    prompt="You are an experienced Python developer.",
                    tools=["Read", "Write", "Bash"],
                )
            },
            permission_mode="acceptEdits",
            env=self.settings.agent_env(),
            mcp_servers={
                "assistant": create_sdk_mcp_server(
                    name="assistant", tools=self._telegram_tools(bot, chat_id)
                )
            },
            system_prompt=(self.settings.workspace_dir / "CLAUDE.md").read_text(encoding="utf-8"),
        )

    @staticmethod
    def _telegram_tools(bot: Any, chat_id: int) -> list[Any]:
        @tool("send_message", "Send a progress message to the user", {"text": str})
        async def send_message(args: dict[str, str]) -> dict[str, list[dict[str, str]]]:
            text = args["text"]
            await bot.send_message(chat_id=chat_id, text=text)
            return {"content": [{"type": "text", "text": "Message sent"}]}

        return [send_message]

    @staticmethod
    async def _prompt(text: str) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "user", "message": {"role": "user", "content": text}}
