"""
rename.py

This file is the cog for the rename command.
It is used to rename a ticket channel to a new name.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""
from discord.ext import commands
from discord import app_commands
import asyncio
import discord
from core.config import ConfigManager
from core.decorators import TaskDecorator
from services.ticket_check_service import is_ticket
from services.ticket_channel_ordering import TicketChannelOrdering


class Rename(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client

    @TaskDecorator.task("Send Embed", False)
    async def send_embed(
        self,
        interaction: discord.Interaction,
        old_name: str,
        new_name: str,
    ) -> None:
        rename_embed = discord.Embed(
            description=(
                f"{interaction.user.mention} has changed the ticket name from "
                f"**{old_name}** to **{new_name}**."
            ),
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        rename_embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        await interaction.edit_original_response(
            embed=rename_embed,
            attachments=[discord.File("assets/Logo.png")],
        )

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name="rename", description="Renames the ticket channel")
    @app_commands.describe(name="The name to rename the ticket to")
    async def rename(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        await self.rename_command(interaction, name)

    @TaskDecorator.task("Rename Command", True)
    async def rename_command(self, interaction: discord.Interaction, name: str) -> None:
        channel: discord.TextChannel = interaction.channel
        old_name: str = channel.name

        channel = await asyncio.wait_for(channel.edit(name=name), timeout=5.0)

        if channel.category is not None:
            position = await asyncio.to_thread(
                TicketChannelOrdering.get_ticket_position,
                channel.category,
                channel,
            )
            if position != channel.position:
                channel = await asyncio.wait_for(
                    channel.edit(position=position),
                    timeout=5.0,
                )

        await self.send_embed(interaction, old_name, name)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Rename(client))
