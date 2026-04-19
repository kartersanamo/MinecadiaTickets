from Assets.functions import get_data, execute, log_commands, task
from Assets.classes import Paginator
from discord.ext import commands
from discord import app_commands
import discord


class BlacklistList(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client

    @task("Send Paginator")
    async def send_paginator(self, interaction: discord.Interaction, data: list) -> None:
        """
        Sends a paginated message containing the provided data.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        data (list): A list of strings to be displayed in the paginated message.

        Returns:
        None: This function does not return any value.
        """
        paginate = Paginator()
        paginate.title = "Blacklisted Users"
        paginate.data = data
        paginate.sep = 5
        await paginate.send(interaction) 

    @task("Get Blacklist Data")
    async def get_blacklist_data(self, interaction: discord.Interaction, rows: list) -> list:
        """
        Retrieves and formats blacklist data for display in a paginated message.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        rows (list): A list of dictionaries, where each dictionary represents a row from the 'blacklists' table.

        Returns:
        list: A list of formatted strings containing user information and reason for blacklisting.
        """
        blacklist_data: list = []
        for row in rows:
            user_id = int(row['userID'])
            staff_id = int(row['staffID'])
            reason = row['reason']
            user: discord.Member = interaction.guild.get_member(user_id)
            staff: discord.Member = interaction.guild.get_member(staff_id)
            if user:
                user_name: str = user.display_name
            else:
                user_name: str = f"`{user_id}`"
            if staff:
                staff_mention: str = staff.mention
            else:
                staff_mention: str = f"`{staff_id}`"
            user_info: str = f"{user_name} ({user_id})"
            reason_info: str = f"`Staff` {staff_mention}\n`Reason` {reason}\n`Unblacklisted` <t:{int(row['whenToUnbl'])}:R>"
            blacklist_data.append(f"**{user_info}**\n{reason_info}\n")
        if not blacklist_data:
            blacklist_data.append("No data found.")
        
        return blacklist_data

    @app_commands.guild_only()
    @app_commands.command(name="blacklist-list", description="Shows all of the users who are blacklisted from tickets")
    async def blacklistlist(self, interaction: discord.Interaction) -> None:
        """
        Executes the 'blacklist-list' command, which displays a paginated list of users blacklisted from tickets.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.

        Returns:
        None: This function does not return any value. It initiates the 'blacklistlist_command' task.
        """
        await self.blacklistlist_command(interaction)

    @task("Blacklist List Command", True)
    async def blacklistlist_command(self, interaction: discord.Interaction) -> None:
        """
        Executes the 'blacklist-list' command, which retrieves and displays a paginated list of users blacklisted from tickets.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.

        Returns:
        None: This function does not return any value. It initiates the following tasks:
            1. Retrieves all rows from the 'blacklists' table.
            2. Formats the blacklist data for display in a paginated message.
            3. Sends the paginated message containing the formatted blacklist data.
        """
        rows: list = execute("SELECT userID, staffID, whenToUnbl, reason FROM blacklists")
        blacklist_data: list = await self.get_blacklist_data(interaction, rows)
        await self.send_paginator(interaction, blacklist_data)

    @blacklistlist.error
    async def blacklistlist_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(BlacklistList(client))