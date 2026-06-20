"""Bot client type with the Minecadia application container."""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from core.app import BotApp


class TicketsBot(commands.Bot):
    app: "BotApp"
