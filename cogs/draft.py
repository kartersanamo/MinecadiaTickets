"""
draft.py

Moves a ticket to the Draft Map category and grants access to draft leaders.

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
from core.discord_helpers import require_guild, require_text_channel
from services.ticket_access_service import TicketAccessService
from services.ticket_channel_ordering import TicketChannelOrdering
from services.ticket_check_service import is_ticket


class Draft(commands.Cog):
    DRAFT_LEADER_IDS = [250708897571143681,]

    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client

    @TaskDecorator.task("Add Draft Leaders", False)
    async def add_draft_leaders(self, channel: discord.TextChannel, guild: discord.Guild) -> list[discord.Member]:
        members = await TicketAccessService.fetch_members(guild, self.DRAFT_LEADER_IDS)
        for member in members:
            perms = channel.overwrites_for(member)
            perms.view_channel = True
            perms.send_messages = True
            perms.embed_links = True
            await channel.set_permissions(member, overwrite=perms)
        return members

    @TaskDecorator.task("Apply Permissions After Move", False)
    async def apply_permissions_after_move(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        category_id: int,
        permissions: list[tuple[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite]],
    ) -> None:
        while channel.category is None or channel.category.id != category_id:
            await asyncio.sleep(0.5)
        await channel.edit(sync_permissions=True)
        for key, value in permissions:
            if isinstance(key, discord.Member):
                await channel.set_permissions(key, overwrite=value)
            elif key == guild.default_role:
                await channel.set_permissions(guild.default_role, overwrite=value)
        staff_team = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        if staff_team is not None:
            await channel.set_permissions(staff_team, view_channel=False)

    @TaskDecorator.task("Update Database", False)
    async def update_database(self, category_name: str, channel_id: int) -> None:
        DatabasePool.execute(
            "UPDATE tickets SET type = %s, privated = 'Admin' WHERE channel_id = %s",
            (category_name, channel_id),
        )

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(
        name="draft",
        description="Moves the ticket to Draft Map and adds draft leaders",
    )
    async def draft(self, interaction: discord.Interaction) -> None:
        await self.draft_command(interaction)

    @TaskDecorator.task("Draft Command", True)
    async def draft_command(self, interaction: discord.Interaction) -> None:
        category_id = TicketAccessService.draft_map_category_id()
        if not category_id:
            await interaction.response.send_message(
                content="`❌` Draft Map category is not configured.",
                ephemeral=True,
            )
            return

        guild = require_guild(interaction.guild)
        channel = require_text_channel(interaction.channel)
        category = guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                content="`❌` Draft Map category was not found.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        permissions = list(channel.overwrites.items())
        position = TicketChannelOrdering.get_ticket_position(category, channel)
        await channel.edit(category=category, position=position, sync_permissions=False)
        await self.update_database(category.name, channel.id)
        await self.apply_permissions_after_move(guild, channel, category.id, permissions)
        leaders = await self.add_draft_leaders(channel, guild)

        leader_mentions = ", ".join(member.mention for member in leaders) or "configured draft leaders"
        embed = discord.Embed(
            description=(
                f"{interaction.user.mention} has moved this ticket to **Draft Map**\n"
                f"-# Draft leaders added: {leader_mentions}"
            ),
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        await interaction.edit_original_response(embed=embed)


async def setup(client: TicketsBot) -> None:
    await client.add_cog(Draft(client))
