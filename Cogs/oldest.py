from Assets.functions import get_data, execute, log_commands, log_tasks, task
from Assets.classes import Paginator
from discord.ext import commands
from discord import app_commands
import discord


class Oldest(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @task("Get Data", False)
    async def get_data_list(self, interaction: discord.Interaction, category: discord.CategoryChannel = None) -> list[str]:
        """
        Retrieves a list of oldest ticket channels from the database.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        category (discord.CategoryChannel, optional): The category of tickets to retrieve. Defaults to None.

        Returns:
        list[str]: A list of oldest ticket channels in the format "{channel.mention} <t:{timestamp}:R>".
        If no data is found, returns a list containing "No data found."
        """
        data: list = []
        bad_channels: list = []
        rows = execute("SELECT channelID, opened_at FROM tickets WHERE active = 'True' ORDER BY opened_at")
        for row in rows:
            channel = interaction.guild.get_channel(int(row['channelID']))
            if channel:
                if category and channel.category_id == category.id:
                    data.append(f"{channel.mention} <t:{(int(float(row['opened_at'])))}:R>")
                else:
                    data.append(f"{channel.mention} <t:{(int(float(row['opened_at'])))}:R>")
            else:
                bad_channels.append(row['channelID'])
        
        if bad_channels:
            bad_channels_str = ', '.join(f"'{channelID}'" for channelID in bad_channels)
            execute(f"UPDATE tickets SET active = 'False' WHERE channelID IN ({bad_channels_str})")
            log_tasks.warning(f"{len(bad_channels)} invalid channel IDs found and removed from the database {bad_channels}")

        if not data:
            data = ["No data found."]

        return data

    
    @task("Send Paginator", False)
    async def send_paginator(self, interaction: discord.Interaction, data: list[str], category: discord.CategoryChannel = None) -> None:
        """
        Sends a paginated message containing the oldest ticket channels.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        data (list[str]): A list of oldest ticket channels in the format "{channel.mention} <t:{timestamp}:R>".
        category (discord.CategoryChannel, optional): The category of tickets to display. Defaults to None.

        Returns:
        None: This function is an asynchronous coroutine and does not return a value.
        """
        paginate = Paginator()
        paginate.title = f"Oldest Tickets in {category.name}" if category else "Oldest Tickets"
        paginate.sep = 15
        paginate.category = category
        paginate.data = data
        paginate.count = True
        await paginate.send(interaction)

    @app_commands.guild_only()
    @app_commands.command(name = "oldest", description = "Displays the oldest tickets that are currently open")
    @app_commands.describe(category = "The category of tickets to display")
    async def oldest(self, interaction: discord.Interaction, category: discord.CategoryChannel = None) -> None:
        """
        Displays the oldest tickets that are currently open in a Discord server.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        category (discord.CategoryChannel, optional): The category of tickets to display. Defaults to None.

        Returns:
        None: This function is an asynchronous coroutine and does not return a value. It sends a deferred response,
        then calls the `oldest_command` method with the provided parameters.
        """
        await self.oldest_command(interaction, category)
    
    @task("Oldest Command", True)
    async def oldest_command(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        """
        Executes the oldest ticket command in a Discord server.

        This function sends a deferred response, retrieves a list of oldest ticket channels from the database,
        and sends a paginated message containing the oldest ticket channels.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        category (discord.CategoryChannel): The category of tickets to display.

        Returns:
        None: This function is an asynchronous coroutine and does not return a value.
        """
        await interaction.response.defer()
        data: list[str] = await self.get_data_list(interaction)
        await self.send_paginator(interaction, data, category)

    @oldest.error
    async def oldest_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Oldest(client))