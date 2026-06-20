"""
private.py

This file is the cog for the private command.
It is used to private a ticket channel so that only Admins can view it.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.discord_helpers import require_category_channel, require_guild, require_text_channel
from core.loggers import log_tasks
from services.ticket_check_service import is_ticket


class Private(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name="private", description="Privates the ticket channel so that only Admins can view it")
    async def private(self, interaction: discord.Interaction) -> None:
        await self.private_command(interaction)

    @TaskDecorator.task("Change Category", False)
    async def change_category(self, channel: discord.TextChannel, category: discord.CategoryChannel) -> None:
        await channel.edit(category=category)

    @TaskDecorator.task("Update Database", False)
    async def update_database(self, channel_id: int, privated_str: str) -> None:
        DatabasePool.execute(
            "UPDATE tickets SET privated = %s WHERE channel_id = %s",
            (privated_str, channel_id),
        )

    @TaskDecorator.task("Update Permissions", False)
    async def update_permissions(
        self, channel: discord.TextChannel, guild: discord.Guild, permissions, default_role: discord.Role
    ) -> None:
        await channel.edit(sync_permissions=True)
        for key, value in permissions:
            if isinstance(key, discord.Member) or key == default_role:
                await channel.set_permissions(key, overwrite=value)
        staff_team = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        if staff_team is not None:
            await channel.set_permissions(staff_team, view_channel=False)

    @TaskDecorator.task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, description: str) -> None:
        embed = discord.Embed(
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
            description=f"{interaction.user.mention} {description}",
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        await interaction.followup.send(embed=embed, file=discord.File("assets/Logo.png"))

    @TaskDecorator.task("Private Command", True)
    async def private_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        guild = require_guild(interaction.guild)
        channel = require_text_channel(interaction.channel)
        category = require_category_channel(guild.get_channel(ConfigManager.get("CHANNEL_IDS")["ADMIN+_CHECK_ID"]))

        await self.change_category(channel, category)
        await self.update_database(channel.id, "Admin")

        def check(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> bool:
            return after.id == channel.id and after.category == category

        try:
            await interaction.client.wait_for("guild_channel_update", check=check, timeout=5)
        except asyncio.TimeoutError:
            if channel.category is None or channel.category.id != category.id:
                log_tasks.warning("Timeout occurred while waiting for the category to update.")
                return await interaction.followup.send(
                    "`❌` Timeout Error! The bot could not change the channel's category. Please try again.",
                    ephemeral=True,
                )

        await self.update_permissions(channel, guild, channel.overwrites.items(), guild.default_role)
        await self.send_embed(interaction, "has turned this channel private.")

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name="management", description="Privates the channel so that only Management can view it")
    async def management(self, interaction: discord.Interaction) -> None:
        await self.management_command(interaction)

    @TaskDecorator.task("Management Command", True)
    async def management_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        guild = require_guild(interaction.guild)
        channel = require_text_channel(interaction.channel)
        category = require_category_channel(
            guild.get_channel(ConfigManager.get("CHANNEL_IDS")["MANAGEMENT_CONTACT_ID"])
        )

        await self.change_category(channel, category)
        await self.update_database(channel.id, "Management")

        def check(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> bool:
            return after.id == channel.id and after.category == category

        try:
            await interaction.client.wait_for("guild_channel_update", check=check, timeout=5)
        except asyncio.TimeoutError:
            if channel.category is None or channel.category.id != category.id:
                log_tasks.warning("Timeout occurred while waiting for the category to update.")
                return await interaction.followup.send(
                    "`❌` Timeout Error! The bot could not change the channel's category. Please try again.",
                    ephemeral=True,
                )

        await self.update_permissions(channel, guild, channel.overwrites.items(), guild.default_role)
        await self.send_embed(interaction, "has made this channel for management.")


async def setup(client: TicketsBot) -> None:
    await client.add_cog(Private(client))
