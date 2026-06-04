from discord.ext import commands
from discord import app_commands
import asyncio
import discord
from core.config import get_data
from core.decorators import task
from core.loggers import log_commands
from domain.checks import is_ticket
from utils.embeds import get_embed_logo_url


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
        logo_url = get_embed_logo_url(self.data["LOGO"])
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

    @rename.error
    async def rename_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        error = error.original
        if isinstance(error, asyncio.TimeoutError):
            error = f"`❌` Failed! You are trying to change the ticket name too quickly!"
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) is trying to change the ticket name too quickly {error}")
        elif isinstance(error, discord.HTTPException):
            error = f"`❌` Try something else! Discord does not allow that channel name."
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to change the ticket name to a disallowed name {error}")
        else:
            log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Rename(client))