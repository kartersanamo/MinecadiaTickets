"""
oldest.py

This file is the cog for the oldest command.
It is used to display the oldest tickets in the server.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""
from discord.ext import commands
from discord import app_commands
import discord
from typing import Optional

from core.bot_client import TicketsBot
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.discord_helpers import require_guild
from core.loggers import log_tasks
from ui.views.paginator import Paginator


class Oldest(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client
    @TaskDecorator.task("Get Data", False)
    async def get_data_list(self, interaction: discord.Interaction, category: Optional[discord.CategoryChannel] = None) -> list[str]:
        data: list = []
        bad_channels: list = []
        guild = require_guild(interaction.guild)
        rows = DatabasePool.execute("SELECT channel_id, opened_at FROM tickets WHERE is_active = 1 ORDER BY opened_at")
        for row in rows:
            channel = guild.get_channel(int(row['channel_id']))
            if channel:
                if category and channel.category_id == category.id:
                    data.append(f"{channel.mention} <t:{(int(float(row['opened_at'])))}:R>")
                else:
                    data.append(f"{channel.mention} <t:{(int(float(row['opened_at'])))}:R>")
            else:
                bad_channels.append(row['channel_id'])
        
        if bad_channels:
            from services.active_ticket_cache import active_ticket_cache

            placeholders = ", ".join(["%s"] * len(bad_channels))
            DatabasePool.execute(
                f"UPDATE tickets SET is_active = 0 WHERE channel_id IN ({placeholders})",
                tuple(bad_channels),
            )
            for channel_id in bad_channels:
                active_ticket_cache.unregister(int(channel_id))
            log_tasks.warning(f"{len(bad_channels)} invalid channel IDs found and removed from the database {bad_channels}")

        if not data:
            data = ["No data found."]

        return data

    
    @TaskDecorator.task("Send Paginator", False)
    async def send_paginator(self, interaction: discord.Interaction, data: list[str], category: Optional[discord.CategoryChannel] = None) -> None:
        paginate = Paginator()
        paginate.title = f"Oldest Tickets in {category.name}" if category else "Oldest Tickets"
        paginate.sep = 15
        paginate.category = category
        paginate.data = data
        paginate.count = True
        await paginate.send(interaction)

    @app_commands.guild_only()
    @app_commands.command(name = "oldest", description = "Displays the oldest tickets that are currently open")
    @app_commands.describe(category = "The category of tickets to display")
    async def oldest(self, interaction: discord.Interaction, category: Optional[discord.CategoryChannel] = None) -> None:
        await self.oldest_command(interaction, category)
    
    @TaskDecorator.task("Oldest Command", True)
    async def oldest_command(self, interaction: discord.Interaction, category: Optional[discord.CategoryChannel]) -> None:
        await interaction.response.defer()
        data: list[str] = await self.get_data_list(interaction, category)
        await self.send_paginator(interaction, data, category)



async def setup(client: TicketsBot) -> None:
    await client.add_cog(Oldest(client))