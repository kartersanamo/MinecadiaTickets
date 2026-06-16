"""One-call wiring for bot main modules."""
from __future__ import annotations

import logging

from discord.ext import commands

from core.errors.discord_handlers import DiscordErrorHandlers


class ErrorSetup:
    @staticmethod
    def wire_bot(
        bot: commands.Bot,
        *,
        bot_name: str,
        log_commands: logging.Logger,
        log_tasks: logging.Logger,
    ) -> None:
        DiscordErrorHandlers.install_error_handlers(
            bot,
            bot_name=bot_name,
            log_commands=log_commands,
            log_tasks=log_tasks,
        )

    @staticmethod
    async def wire_bot_async_setup(
        bot: commands.Bot,
        *,
        bot_name: str,
        log_tasks: logging.Logger,
    ) -> None:
        DiscordErrorHandlers.install_asyncio_exception_handler(bot, log_tasks=log_tasks, bot_name=bot_name)
