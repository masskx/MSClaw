"""Telegram transport and application entry point."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .agent import AgentError, AgentService
from .config import ConfigurationError, Settings
from .storage import FileStorage

LOGGER = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 4000


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    return [text[index : index + limit] for index in range(0, len(text), limit)] or [""]


class TelegramHandlers:
    def __init__(self, settings: Settings, storage: FileStorage, agent: AgentService) -> None:
        self.settings = settings
        self.storage = storage
        self.agent = agent

    def is_owner(self, update: Update) -> bool:
        return bool(update.effective_user and update.effective_user.id == self.settings.owner_id)

    async def _authorize(self, update: Update) -> bool:
        if self.is_owner(update):
            return True
        if update.effective_message:
            await update.effective_message.reply_text("You are not authorized to use this bot.")
        LOGGER.warning("Rejected unauthorized Telegram update")
        return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._authorize(update) and update.effective_message:
            await update.effective_message.reply_text(
                f"{self.settings.assistant_name} is ready. Send me a task."
            )

    async def clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if await self._authorize(update) and update.effective_message:
            cleared = self.storage.clear_session_id()
            message = (
                "Conversation session cleared." if cleared else "No active session was stored."
            )
            await update.effective_message.reply_text(message)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorize(update):
            return
        message = update.effective_message
        chat = update.effective_chat
        if not message or not message.text or not chat:
            return

        try:
            response = await self.agent.run(message.text, context.bot, chat.id)
            self.storage.archive_conversation(message.text, response)
        except AgentError:
            LOGGER.exception("Agent returned no final response")
            await message.reply_text("The agent did not return a final response. Please try again.")
            return
        except Exception:
            LOGGER.exception("Failed to process Telegram message")
            await message.reply_text("The request failed unexpectedly. Please try again later.")
            return

        for chunk in split_message(response):
            await message.reply_text(chunk)


def build_application(settings: Settings) -> Application[Any, Any, Any, Any, Any, Any]:
    storage = FileStorage(settings.data_dir, settings.workspace_dir, settings.assistant_name)
    storage.ensure_workspace()
    handlers = TelegramHandlers(settings, storage, AgentService(settings, storage))
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("clear", handlers.clear))
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )
    return application


def main() -> None:
    load_dotenv(override=False)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        settings = Settings.from_env(project_dir=Path.cwd())
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc
    LOGGER.info("Starting %s with workspace %s", settings.assistant_name, settings.workspace_dir)
    build_application(settings).run_polling()
