"""Register analytics cogs on this bot."""

from __future__ import annotations

from discord.ext import commands

from core.analytics.command_usage import CommandUsageCog


class CommandTrackingRegistrar:
    @staticmethod
    async def register_command_tracking(bot: commands.Bot) -> None:
        if "AnalyticsTracking" in bot.cogs:
            return

        await CommandUsageCog.setup(client=bot)
