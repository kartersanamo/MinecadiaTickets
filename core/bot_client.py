"""Bot client type with the Minecadia application container."""

from __future__ import annotations

from discord.ext import commands

from core.app import BotApp


class TicketsBot(commands.Bot):
    app: BotApp
