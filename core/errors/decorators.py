"""Decorators for safe UI callbacks and tasks."""
from __future__ import annotations

import functools
import logging
from typing import Callable, TypeVar

import discord

from core.errors.interactions import SafeInteractions
from core.errors.logging import ExceptionLogging
from core.errors.messages import ErrorMessages

F = TypeVar("F", bound=Callable)


class SafeInteractionDecorator:
    @staticmethod
    def safe_interaction(
        logger: logging.Logger,
        *,
        bot_name: str | None = None,
        user_message: str | None = None,
        component: str | None = None,
    ) -> Callable[[F], F]:
        """Wrap a view/modal callback: log failures and reply ephemerally."""

        def decorator(func: F) -> F:
            @functools.wraps(func)
            async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
                try:
                    return await func(self, interaction, *args, **kwargs)
                except Exception as exc:
                    msg = user_message or ErrorMessages.external_service_message(exc)
                    ExceptionLogging.log_exception(
                        logger,
                        exc,
                        bot_name=bot_name,
                        interaction=interaction,
                        component=component or func.__name__,
                    )
                    await SafeInteractions.safe_reply(interaction, content=f"`❌` {msg}", ephemeral=True)

            return wrapper  # type: ignore

        return decorator
