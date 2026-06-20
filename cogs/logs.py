"""
logs.py

This file is the cog for the logs command. It is used to display
the logs of the tickets in the server and the number of tickets open.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

import discord
from discord.ext import commands, tasks

from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.loggers import log_commands


class Logs(commands.Cog):
    def __init__(self, client: TicketsBot):
        self.client: TicketsBot = client

    @commands.Cog.listener()
    async def on_ready(self):
        # await self.update_ticket_vc_count_loop.start() Turned off due to rate limits
        pass

    @TaskDecorator.task("Get Ticket Count")
    async def get_ticket_count(self) -> int:
        row = await DatabasePool.aexecute("SELECT COUNT(*) AS n FROM tickets WHERE is_active = %s", (1,))
        if not row:
            return 0
        return int(row[0].get("n") or row[0].get("COUNT(*)") or 0)

    @TaskDecorator.task("Update Ticket VC Count")
    async def update_ticket_vc_count(self) -> None:
        new_ticket_count: int = await self.get_ticket_count()
        guild = self.client.get_guild(ConfigManager.get("GUILD_ID"))
        if guild is None:
            return
        channel = guild.get_channel(ConfigManager.get("CHANNEL_IDS")["TICKET_COUNT_VOICE_CHANNEL_ID"])
        if channel is None:
            return
        await channel.edit(name=f"Tickets: {new_ticket_count}")

    @tasks.loop(minutes=5)
    async def update_ticket_vc_count_loop(self):
        await self.update_ticket_vc_count()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            if interaction.command is None:
                return
            name = f"/{interaction.command.name}"
            try:
                options = interaction.data.get("options") if interaction.data else None
                for option in options or []:
                    value = option.get("value")
                    if value is not None:
                        name += f" {option['name']}:'{value}'"
            except KeyError:
                pass
            channel_ref = interaction.channel
            channel_name = getattr(channel_ref, "name", "unknown")
            channel_id = getattr(channel_ref, "id", "unknown")
            log_commands.info(
                "%s (%s) ran %s in #%s (%s) %s",
                interaction.user,
                interaction.user.id,
                name,
                channel_name,
                channel_id,
                not interaction.command_failed,
            )


async def setup(client: TicketsBot) -> None:
    await client.add_cog(Logs(client))
