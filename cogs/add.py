"""
add.py

This file is the cog for the add command.
It is used to add a user to a ticket channel so that they can view it.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

import discord
from discord import app_commands
from discord.ext import commands

from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.discord_helpers import require_text_channel
from core.loggers import log_commands
from services.ticket_check_service import is_ticket


class Add(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client

    @TaskDecorator.task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        channel = require_text_channel(interaction.channel)
        rows = DatabasePool.execute("SELECT 1 FROM blacklists WHERE user_id = %s LIMIT 1", (user.id,))
        if rows:
            log_commands.warning(
                "Failed to add %s (%s) to #%s (%s) as they are ticket blacklisted",
                user,
                user.id,
                channel.name,
                channel.id,
            )
            await interaction.response.send_message(
                content=(
                    "`❌` Failed! You cannot add this player to the ticket "
                    "as they are currently ticket blacklisted!"
                ),
                ephemeral=True,
            )
            return True
        return False

    @TaskDecorator.task("Check Timed Out", False)
    async def check_timed_out(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        channel = require_text_channel(interaction.channel)
        if user.is_timed_out():
            log_commands.warning(
                "Failed to add %s (%s) to #%s (%s) as they are timed out",
                user,
                user.id,
                channel.name,
                channel.id,
            )
            await interaction.response.send_message(
                content="`❌` Failed! You cannot add this player to the ticket as they are currently timed out!",
                ephemeral=True,
            )
            return True
        return False

    @staticmethod
    def is_staff_member(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            return False
        staff_role = interaction.guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        return staff_role is not None and staff_role in interaction.user.roles

    @TaskDecorator.task("Check Ticket Owner", False)
    async def check_ticket_owner(self, interaction: discord.Interaction) -> bool:
        if self.is_staff_member(interaction):
            return False
        channel = require_text_channel(interaction.channel)
        rows = DatabasePool.execute(
            "SELECT owner_id FROM tickets WHERE channel_id = %s AND is_active = 1 LIMIT 1",
            (channel.id,),
        )
        if not rows or int(rows[0]["owner_id"]) != interaction.user.id:
            await interaction.response.send_message(
                content="`❌` Failed! Only the ticket owner can add players to this ticket.",
                ephemeral=True,
            )
            return True
        return False

    @TaskDecorator.task("Check Added Players", False)
    async def check_added_players(self, interaction: discord.Interaction) -> bool:
        if self.is_staff_member(interaction):
            return False
        channel = require_text_channel(interaction.channel)
        rows = DatabasePool.execute(
            "SELECT owner_id FROM tickets WHERE channel_id = %s AND is_active = 1 LIMIT 1",
            (channel.id,),
        )
        if not rows:
            return True

        owner_id = int(rows[0]["owner_id"])
        added_players = sum(
            1
            for target, overwrite in channel.overwrites.items()
            if isinstance(target, discord.Member)
            and target.id != owner_id
            and overwrite.view_channel is True
        )
        if added_players >= 2:
            await interaction.response.send_message(
                content="`❌` Failed! You can only add up to **2** players to your ticket.",
                ephemeral=True,
            )
            return True
        return False

    @TaskDecorator.task("Set Permissions", False)
    async def set_permissions(self, channel: discord.TextChannel, user: discord.Member) -> None:
        from services.ticket_access_service import TicketAccessService

        await TicketAccessService.grant_user_channel_access(channel, user)

    @TaskDecorator.task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, user: discord.Member) -> None:
        channel = require_text_channel(interaction.channel)
        embed = discord.Embed(
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
            description=f"{interaction.user.mention} has added {user.mention} to the ticket {channel.mention}",
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        await interaction.response.send_message(embed=embed, file=discord.File("assets/Logo.png"))

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name="add", description="Adds a user to the ticket")
    @app_commands.describe(user="The user to add to the ticket")
    async def add(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.add_command(interaction, user)

    @TaskDecorator.task("Add Command", True)
    async def add_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        not_owner: bool = await self.check_ticket_owner(interaction)
        if not_owner:
            return
        limit_reached: bool = await self.check_added_players(interaction)
        if limit_reached:
            return
        blacklisted: bool = await self.check_blacklisted(interaction, user)
        timed_out: bool = await self.check_timed_out(interaction, user)

        if not blacklisted and not timed_out:
            channel = require_text_channel(interaction.channel)
            await self.set_permissions(channel, user)
            await self.send_embed(interaction, user)


async def setup(client: TicketsBot) -> None:
    await client.add_cog(Add(client))
