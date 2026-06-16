"""
blacklist_list.py

This file is the cog for the blacklist list command.
It is used to display the list of users who are blacklisted from opening tickets.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""
from discord.ext import commands
from discord import app_commands
import discord
from core.database import execute
from core.decorators import task
from ui.views.paginator import Paginator


class BlacklistList(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client

    @task("Send Paginator")
    async def send_paginator(self, interaction: discord.Interaction, data: list) -> None:
        paginate = Paginator()
        paginate.title = "Blacklisted Users"
        paginate.data = data
        paginate.sep = 5
        await paginate.send(interaction) 

    @task("Get Blacklist Data")
    async def get_blacklist_data(self, interaction: discord.Interaction, rows: list) -> list:
        blacklist_data: list = []
        for row in rows:
            user_id = int(row['user_id'])
            staff_id = int(row['staff_id'])
            reason = row['reason']
            user: discord.Member = interaction.guild.get_member(user_id)
            staff: discord.Member = interaction.guild.get_member(staff_id)
            if user:
                user_name: str = user.display_name
            else:
                user_name: str = f"`{user_id}`"
            if staff:
                staff_mention: str = staff.mention
            else:
                staff_mention: str = f"`{staff_id}`"
            user_info: str = f"{user_name} ({user_id})"
            reason_info: str = f"`Staff` {staff_mention}\n`Reason` {reason}\n`Unblacklisted` <t:{int(row['unblacklist_at'])}:R>"
            blacklist_data.append(f"**{user_info}**\n{reason_info}\n")
        if not blacklist_data:
            blacklist_data.append("No data found.")
        
        return blacklist_data

    @app_commands.guild_only()
    @app_commands.command(name="blacklist-list", description="Shows all of the users who are blacklisted from tickets")
    async def blacklistlist(self, interaction: discord.Interaction) -> None:
        await self.blacklistlist_command(interaction)

    @task("Blacklist List Command", True)
    async def blacklistlist_command(self, interaction: discord.Interaction) -> None:
        rows: list = execute("SELECT user_id, staff_id, unblacklist_at, reason FROM blacklists")
        blacklist_data: list = await self.get_blacklist_data(interaction, rows)
        await self.send_paginator(interaction, blacklist_data)



async def setup(client: commands.Bot) -> None:
    await client.add_cog(BlacklistList(client))