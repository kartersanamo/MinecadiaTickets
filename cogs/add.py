"""
add.py

This file is the cog for the add command.
It is used to add a user to a ticket channel so that they can view it.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""
from discord.ext import commands
from discord import app_commands
import discord
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.loggers import log_commands
from services.ticket_check_service import is_ticket


class Add(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
    @TaskDecorator.task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        rows = DatabasePool.execute("SELECT 1 FROM blacklists WHERE user_id = %s LIMIT 1", (user.id,))
        if rows:
            log_commands.warning(f"Failed to add {user} ({user.id}) to #{interaction.channel.name} ({interaction.channel.id}) as they are ticket blacklisted")
            await interaction.response.send_message(content = "`❌` Failed! You cannot add this player to the ticket as they are currently ticket blacklisted!", ephemeral = True)
            return True
        return False

    @TaskDecorator.task("Check Timed Out", False)    
    async def check_timed_out(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        if user.is_timed_out():
            log_commands.warning(f"Failed to add {user} ({user.id}) to #{interaction.channel.name} ({interaction.channel.id}) as they are timed out")
            await interaction.response.send_message(content = "`❌` Failed! You cannot add this player to the ticket as they are currently timed out!", ephemeral = True)
            return True
        return False

    @TaskDecorator.task("Set Permissions", False)
    async def set_permissions(self, channel: discord.TextChannel, user: discord.Member) -> None:
        perms = channel.overwrites_for(user)
        perms.view_channel = True
        perms.send_messages = True
        await channel.set_permissions(user, overwrite=perms)

    @TaskDecorator.task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, user: discord.Member) -> None:
        embed = discord.Embed(
            color = discord.Color.from_str(ConfigManager.get("EMBED_COLOR")), 
            description = f"{interaction.user.mention} has added {user.mention} to the ticket {interaction.channel.mention}"
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text = ConfigManager.get("FOOTER"), icon_url = logo_url)
        await interaction.response.send_message(embed = embed, file = discord.File("assets/Logo.png"))

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "add", description = "Adds a user to the ticket")
    @app_commands.describe(user = "The user to add to the ticket")
    async def add(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.add_command(interaction, user)

    @TaskDecorator.task("Add Command", True)
    async def add_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        blacklisted: bool = await self.check_blacklisted(interaction, user)
        timed_out: bool = await self.check_timed_out(interaction, user)
        
        if not blacklisted and not timed_out:
            await self.set_permissions(interaction.channel, user)
            await self.send_embed(interaction, user)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Add(client))