"""
move.py

This file is the cog for the move command.
It is used to move a ticket to a new category.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""
from discord.ext import commands
from discord import app_commands
import discord
import asyncio
from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.discord_helpers import require_guild, require_text_channel
from core.loggers import log_commands
from services.ticket_check_service import is_ticket
from services.ticket_channel_ordering import TicketChannelOrdering


class Move(commands.Cog):
    def __init__(self, client: TicketsBot):
        self.client: TicketsBot = client
    @TaskDecorator.task("Defer Response", False)
    async def defer_response(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    @TaskDecorator.task("Check Blacklisted", False)
    async def check_blacklisted_category(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> bool:
        if category.id in ConfigManager.get('BLACKLISTED_MOVE_CATEGORIES'):
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to move a ticket to a blacklisted category {category} ({category.id})")
            await interaction.response.send_message(content = "`❌` Failed! You cannot move a ticket to this category!", ephemeral = True)
            return True
        return False

    @TaskDecorator.task("Check Category", False)
    async def check_ticket_category(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> bool:
        if category.id not in ConfigManager.get("TICKET_CATEGORIES"):
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to move a ticket to a non-ticket category {category} ({category.id})")
            await interaction.response.send_message(content = "`❌` Failed! That is not a ticket category!", ephemeral = True)
            return True
        return False

    @TaskDecorator.task("Move Categories", False)
    async def move_categories(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        channel = require_text_channel(interaction.channel)
        position = TicketChannelOrdering.get_ticket_position(category, channel)
        await channel.edit(category = category, position = position)

    @TaskDecorator.task("Update Database", False)
    async def update_database(self, category_name: str, channel_id: int) -> None:
        if category_name == "Admin+ Check":
            DatabasePool.execute(
                "UPDATE tickets SET privated = 'Admin' WHERE channel_id = %s",
                (channel_id,),
            )
        elif category_name == "Store Issue Tickets":
            DatabasePool.execute(
                "UPDATE tickets SET type = %s, privated = 'Admin' WHERE channel_id = %s",
                (category_name, channel_id),
            )
        elif category_name == "Management Contact":
            DatabasePool.execute(
                "UPDATE tickets SET type = %s, privated = 'Management' WHERE channel_id = %s",
                (category_name, channel_id),
            )
        else:
            DatabasePool.execute(
                "UPDATE tickets SET type = %s, privated = '' WHERE channel_id = %s",
                (category_name, channel_id),
            )

    @TaskDecorator.task("Set Permissions", False)
    async def set_permissions(self, interaction: discord.Interaction, new_category_id: int) -> None:
        guild = require_guild(interaction.guild)
        channel = require_text_channel(interaction.channel)
        permissions = channel.overwrites.items()
        while channel.category is None or channel.category.id != new_category_id:
            await asyncio.sleep(0.5)
        await channel.edit(sync_permissions = True)
        for key, value in permissions:
            if isinstance(key, (discord.Member, discord.Role)):
                await channel.set_permissions(key, overwrite = value)
        staff_team = guild.get_role(ConfigManager.get('ROLE_IDS')['STAFF_TEAM_ROLE_ID'])
        if staff_team is not None:
            await channel.set_permissions(staff_team, view_channel = False)

    @TaskDecorator.task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, category_name: str) -> None:
        confirmation_embed = discord.Embed(
            description = f"{interaction.user.mention} has moved this ticket to **{category_name}**", 
            color = discord.Color.from_str(ConfigManager.get("EMBED_COLOR"))
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        confirmation_embed.set_footer(text = ConfigManager.get("FOOTER"), icon_url = logo_url) 
        await interaction.edit_original_response(embed = confirmation_embed)

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "move", description = "Moves a ticket to a new category")
    @app_commands.describe(category = "The category to move the ticket to")
    async def move(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        await self.move_command(interaction, category)

    @TaskDecorator.task("Move Command", True)
    async def move_command(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        blacklisted_category = await self.check_blacklisted_category(interaction, category)
        not_a_ticket_category = await self.check_ticket_category(interaction, category) 
        if not blacklisted_category and not not_a_ticket_category:
            await self.defer_response(interaction)
            channel = require_text_channel(interaction.channel)
            await self.move_categories(interaction, category)
            await self.update_database(category.name, channel.id)
            await self.set_permissions(interaction, category.id)
            await self.send_embed(interaction, category.name)



async def setup(client: TicketsBot) -> None:
    await client.add_cog(Move(client))