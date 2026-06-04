from discord.ext import commands
from discord import app_commands
import asyncio
import discord
from core.config import get_data
from core.decorators import task
from core.loggers import log_commands
from services.ticket_check_service import is_ticket


class Rename(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @task("Edit Name", False)
    async def edit_channel_name(self, channel: discord.TextChannel, name: str):
        return await channel.edit(name = name)

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, old_name: str) -> None:
        rename_embed = discord.Embed(
            description = f"{interaction.user.mention} has changed the ticket name from **{old_name}** to **{interaction.channel.name}**.", 
            color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        logo_url = self.client.app.embeds.get_logo_url(self.data["LOGO"])
        rename_embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
        await interaction.response.send_message(embed = rename_embed, file = discord.File("assets/Logo.png"))

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "rename", description = "Renames the ticket channel")
    @app_commands.describe(name = "The name to rename the ticket to")
    async def rename(self, interaction: discord.Interaction, name: str):
        await self.rename_command(interaction, name)

    @task("Rename Command", True)
    async def rename_command(self, interaction: discord.Interaction, name: str) -> None:
        old_name: str = interaction.channel.name
        await asyncio.wait_for(self.edit_channel_name(interaction.channel, name), timeout = 2.0)
        await interaction.channel.edit(name = name)
        await self.send_embed(interaction, old_name)



async def setup(client: commands.Bot) -> None:
    await client.add_cog(Rename(client))