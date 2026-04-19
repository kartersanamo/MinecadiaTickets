from Assets.functions import get_data, is_ticket, log_commands, task
from discord.ext import commands
from discord import app_commands
import asyncio
import discord


class Rename(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @task("Edit Name", False)
    async def edit_channel_name(self, channel: discord.TextChannel, name: str):
        """
        Asynchronously edits the name of a given text channel.

        Parameters:
        - channel (discord.TextChannel): The text channel to be edited.
        - name (str): The new name for the text channel.

        Returns:
        - discord.TextChannel: The edited text channel.

        Raises:
        - discord.HTTPException: If the Discord API returns an error.
        """
        return await channel.edit(name = name)

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, old_name: str) -> None:
        """
        Sends an embed message to the interaction response with ticket rename information.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object that triggered this function.
        - old_name (str): The original name of the ticket channel.

        Returns:
        - None: This function is an asynchronous coroutine and does not return a value.

        Raises:
        - discord.HTTPException: If the Discord API returns an error while sending the message.
        """
        rename_embed = discord.Embed(
            description = f"{interaction.user.mention} has changed the ticket name from **{old_name}** to **{interaction.channel.name}**.", 
            color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        from Assets.functions import get_embed_logo_url
        logo_url = get_embed_logo_url(self.data["LOGO"])
        rename_embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
        await interaction.response.send_message(embed = rename_embed, file = discord.File("Assets/Logo.png"))

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "rename", description = "Renames the ticket channel")
    @app_commands.describe(name = "The name to rename the ticket to")
    async def rename(self, interaction: discord.Interaction, name: str):
        """
        Renames the ticket channel.

        This function is a Discord interaction command that renames a ticket channel.
        It is only available in guilds and requires the user to have the 'is_ticket' check.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object that triggered this function.
        - name (str): The new name for the ticket channel.

        Returns:
        - None: This function is an asynchronous coroutine and does not return a value.

        Raises:
        - discord.HTTPException: If the Discord API returns an error while renaming the channel.
        """
        await self.rename_command(interaction, name)

    @task("Rename Command", True)
    async def rename_command(self, interaction: discord.Interaction, name: str) -> None:
        """
        Renames the ticket channel asynchronously and sends an embed message.

        This function is responsible for renaming a ticket channel,
        waiting for the operation to complete, sending an embed message to the interaction response,
        and logging relevant information.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object that triggered this function.
        - name (str): The new name for the ticket channel.

        Returns:
        - None: This function is an asynchronous coroutine and does not return a value.

        Raises:
        - asyncio.TimeoutError: If the operation to rename the channel takes longer than 2 seconds.
        - discord.HTTPException: If the Discord API returns an error while renaming the channel or sending the message.
        """
        old_name: str = interaction.channel.name
        await asyncio.wait_for(self.edit_channel_name(interaction.channel, name), timeout = 2.0)
        await interaction.channel.edit(name = name)
        await self.send_embed(interaction, old_name)

    @rename.error
    async def rename_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """
        Handles errors that occur during the renaming of a ticket channel.

        This function is a Discord interaction error handler for the 'rename' command.
        It checks the type of error that occurred and sends a corresponding error message to the user.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object that triggered this function.
        - error (discord.app_commands.AppCommandError): The error that occurred during the 'rename' command execution.

        Returns:
        - None: This function is an asynchronous coroutine and does not return a value.

        Raises:
        - discord.HTTPException: If the Discord API returns an error while sending the error message.
        """
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