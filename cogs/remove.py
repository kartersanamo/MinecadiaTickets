"""
remove.py

This file is the cog for the remove command.
It is used to remove a user from a ticket channel.

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
from core.discord_helpers import require_guild, require_text_channel
from core.loggers import log_commands
from services.ticket_check_service import is_ticket


class Remove(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client

    @staticmethod
    def _hierarchy_role_ids() -> set[int]:
        return {role_id for roles in ConfigManager.get("ROLE_HIERARCHY").values() for role_id in roles}

    @classmethod
    def _get_comparison_role_id(cls, member: discord.Member) -> int | None:
        disregard_role_ids = set(ConfigManager.get("DISREGARD_REMOVE_COMMAND_ROLE_IDS"))
        hierarchy_role_ids = cls._hierarchy_role_ids()
        for role in reversed(member.roles):
            if role.id in disregard_role_ids:
                continue
            if role.id in hierarchy_role_ids:
                return role.id
        return None

    @TaskDecorator.task("Get Role Level", False)
    async def get_role_level(self, role_id: int) -> int | None:
        for level, roles in enumerate(ConfigManager.get("ROLE_HIERARCHY").values()):
            if role_id in roles:
                return level
        return None

    @TaskDecorator.task("Is Higher Rank", False)
    async def is_higher_rank(self, role_id1: int, role_id2: int) -> bool:
        level1 = await self.get_role_level(role_id1)
        level2 = await self.get_role_level(role_id2)
        if level1 is None or level2 is None:
            return False
        return level1 > level2

    @TaskDecorator.task("Remove Permissions", False)
    async def remove_permissions(self, channel: discord.TextChannel, user: discord.Member) -> None:
        perms = channel.overwrites_for(user)
        perms.view_channel = False
        await channel.set_permissions(user, overwrite=perms)

    @TaskDecorator.task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, user: discord.Member) -> None:
        channel = require_text_channel(interaction.channel)
        embed = discord.Embed(
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
            description=f"{interaction.user.mention} has removed {user.mention} from the ticket {channel.mention}",
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        await interaction.response.send_message(embed=embed, file=discord.File("assets/Logo.png"))

    @TaskDecorator.task("Check Higher Rank", False)
    async def check_higher_rank(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        guild = require_guild(interaction.guild)
        staff_team_role = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        if staff_team_role is None or staff_team_role not in user.roles:
            return False
        role_id_1 = self._get_comparison_role_id(user)
        role_id_2 = self._get_comparison_role_id(interaction.user)
        if role_id_1 is None or role_id_2 is None:
            return False
        if await self.is_higher_rank(role_id_1, role_id_2):
            log_commands.warning(
                "%s (%s) tried to remove a staff member higher than them %s (%s)",
                interaction.user,
                interaction.user.id,
                user,
                user.id,
            )
            await interaction.response.send_message(
                content="You cannot remove a staff member who is higher than you!", ephemeral=True
            )
            return True
        return False

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name="remove", description="Removes a user from the ticket")
    @app_commands.describe(user="The user to remove from the ticket")
    async def remove(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.remove_command(interaction, user)

    @TaskDecorator.task("Check Protected User", False)
    async def check_protected_user(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        channel = require_text_channel(interaction.channel)
        rows = DatabasePool.execute("SELECT owner_id FROM tickets WHERE channel_id = %s LIMIT 1", (channel.id,))
        if rows and int(rows[0]["owner_id"]) == user.id:
            await interaction.response.send_message(
                content="`❌` Failed! You cannot remove the ticket owner from their ticket.",
                ephemeral=True,
            )
            return True

        return False

    @TaskDecorator.task("Remove Command", True)
    async def remove_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        protected_user: bool = await self.check_protected_user(interaction, user)
        if protected_user:
            return
        removing_higher: bool = await self.check_higher_rank(interaction, user)
        if not removing_higher:
            channel = require_text_channel(interaction.channel)
            await self.remove_permissions(channel, user)
            await self.send_embed(interaction, user)


async def setup(client: TicketsBot) -> None:
    await client.add_cog(Remove(client))
