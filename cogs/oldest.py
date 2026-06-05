from discord.ext import commands
from discord import app_commands
import discord
from core.config import ConfigManager
from core.database import execute
from core.decorators import task
from core.loggers import log_commands, log_tasks
from ui.views.paginator import Paginator


class Oldest(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
    @task("Get Data", False)
    async def get_data_list(self, interaction: discord.Interaction, category: discord.CategoryChannel = None) -> list[str]:
        data: list = []
        bad_channels: list = []
        rows = execute("SELECT channelID, opened_at FROM tickets WHERE active = 'True' ORDER BY opened_at")
        for row in rows:
            channel = interaction.guild.get_channel(int(row['channelID']))
            if channel:
                if category and channel.category_id == category.id:
                    data.append(f"{channel.mention} <t:{(int(float(row['opened_at'])))}:R>")
                else:
                    data.append(f"{channel.mention} <t:{(int(float(row['opened_at'])))}:R>")
            else:
                bad_channels.append(row['channelID'])
        
        if bad_channels:
            from services.active_ticket_cache import active_ticket_cache

            bad_channels_str = ', '.join(f"'{channelID}'" for channelID in bad_channels)
            execute(f"UPDATE tickets SET active = 'False' WHERE channelID IN ({bad_channels_str})")
            for channel_id in bad_channels:
                active_ticket_cache.unregister(int(channel_id))
            log_tasks.warning(f"{len(bad_channels)} invalid channel IDs found and removed from the database {bad_channels}")

        if not data:
            data = ["No data found."]

        return data

    
    @task("Send Paginator", False)
    async def send_paginator(self, interaction: discord.Interaction, data: list[str], category: discord.CategoryChannel = None) -> None:
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
    async def oldest(self, interaction: discord.Interaction, category: discord.CategoryChannel = None) -> None:
        await self.oldest_command(interaction, category)
    
    @task("Oldest Command", True)
    async def oldest_command(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        await interaction.response.defer()
        data: list[str] = await self.get_data_list(interaction)
        await self.send_paginator(interaction, data, category)



async def setup(client: commands.Bot) -> None:
    await client.add_cog(Oldest(client))