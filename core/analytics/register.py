"""Register analytics cogs on this bot."""

from __future__ import annotations

from discord.ext import commands

from core.analytics.command_usage import CommandUsageCog


class CommandTrackingRegistrar:
    @staticmethod
    def is_registered(bot: commands.Bot) -> bool:
        return "AnalyticsTracking" in bot.cogs

    @staticmethod
    async def register_command_tracking(bot: commands.Bot) -> None:
        if CommandTrackingRegistrar.is_registered(bot):
            return

        await CommandUsageCog.setup(client=bot)
