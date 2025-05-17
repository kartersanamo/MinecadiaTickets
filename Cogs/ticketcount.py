from Assets.functions import get_data, execute, log_commands, task
from discord.ext import commands
from discord import app_commands
from typing import Literal
import discord

class TicketCount(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @task("Get Active List", False)
    async def get_active_list(self) -> list[dict]:
        """
        Retrieves a list of ticket types and their respective counts from the database,
        specifically for active tickets.

        Parameters:
        self (TicketCount): An instance of the TicketCount class.

        Returns:
        list[dict]: A list of dictionaries, where each dictionary contains 'type' and 'count' keys.
                    The 'type' key represents the ticket type, and the 'count' key represents the number
                    of active tickets of that type. The list is sorted in descending order based on the count.
        """
        rows = execute("SELECT type, COUNT(*) as count FROM tickets WHERE active = 'True' GROUP BY type ORDER BY count DESC")
        return rows

    @task("Get Total List", False)
    async def get_total_list(self) -> list[dict]:
        """
        Retrieves a list of ticket types and their respective counts from the database.
        This gets all tickets, regardless of their active status.

        Parameters:
        self (TicketCount): An instance of the TicketCount class.

        Returns:
        list[dict]: A list of dictionaries, where each dictionary contains 'type' and 'count' keys.
                    The 'type' key represents the ticket type, and the 'count' key represents the number
                    of tickets of that type. The list is sorted in descending order based on the count.
        """
        rows = execute("SELECT type, COUNT(*) as count FROM tickets GROUP BY type ORDER BY count DESC")
        return rows

    @task("Get Debug Embeds", False)
    async def get_debug_embeds(self, active_list: list[dict], active_count: int, total_list: list[dict], total_count: int) -> list[discord.Embed]:
        """
        Generates a list of two Discord embeds, one for active tickets and another for total ticket history.

        Parameters:
        self (TicketCount): An instance of the TicketCount class.
        active_list (list[dict]): A list of dictionaries, where each dictionary contains 'type' and 'count' keys.
                                The 'type' key represents the ticket type, and the 'count' key represents the number
                                of active tickets of that type. The list is sorted in descending order based on the count.
        active_count (int): The total number of active tickets.
        total_list (list[dict]): A list of dictionaries, where each dictionary contains 'type' and 'count' keys.
                                The 'type' key represents the ticket type, and the 'count' key represents the number
                                of tickets of that type. The list is sorted in descending order based on the count.
        total_count (int): The total number of tickets.

        Returns:
        list[discord.Embed]: A list containing two Discord embeds. The first embed represents active tickets,
                            and the second embed represents total ticket history.
        """
        active_embed = discord.Embed(
                title = "Active Tickets By Category",
                description = "\n".join(f"> **{row.get('count', 0)}** {row.get('type', 'Unknown')} ({round(row.get('count', 0) / active_count * 100, 2)}%)" for row in active_list),
                color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        active_embed.set_footer(text=f"There are {active_count:,} tickets open!")
        history_embed = discord.Embed(
            title = "Total Ticket History",
            description = "\n".join(f"> **{row.get('count', 0)}** {row.get('type', 'Unknown')} ({round(row.get('count', 0) / total_count * 100, 2)}%)" for row in total_list),
            color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        history_embed.set_footer(text=f"There have been {total_count:,} total tickets!")
        return [active_embed, history_embed]

    @app_commands.guild_only()
    @app_commands.command(name = "ticket-count", description = "Sends the number of currently opened tickets")
    async def ticketcount(self, interaction: discord.Interaction, debug: Literal['Yes'] = None):
        """
        This function is a Discord slash command that sends the number of currently opened tickets.
        It can also provide a debug mode that provides more detailed information about the ticket types.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this command.
        debug (Literal['Yes'], optional): If provided with the value 'Yes', the function will provide a debug mode.
                                        Defaults to None.

        Returns:
        None: This function is asynchronous and does not return any value. It sends a message to the Discord interaction.
        """
        await self.ticket_count_command(interaction, debug)

    @task("Ticket Count Command", True)
    async def ticket_count_command(self, interaction: discord.Interaction, debug: str) -> None:
        """
        This function is responsible for handling the ticket count command.
        It retrieves the count of active and total tickets, and generates appropriate embeds based on the debug mode.

        Parameters:
        self (TicketCount): An instance of the TicketCount class.
        interaction (discord.Interaction): The Discord interaction object that triggered this command.
        debug (str): A string indicating whether debug mode is enabled. If not provided or set to 'None', debug mode is disabled.

        Returns:
        None: This function is asynchronous and does not return any value. It sends a message to the Discord interaction.
        """
        active_list: list[dict] = await self.get_active_list()
        active_count: int = sum(row.get('count', 0) for row in active_list)

        total_list: list[dict] = await self.get_total_list()
        total_count: int = sum(row.get('count', 0) for row in total_list)

        embed_list: list[discord.Embed] = []

        if not debug:
            embed = discord.Embed(
                title = f"There are **{active_count}** tickets open!", 
                color = discord.Color.from_str(self.data["EMBED_COLOR"])
            )
            embed.set_footer(text=f"There have been {total_count:,} total tickets!")
            embed_list.append(embed)
        else:
            debug_embeds: list[discord.Embed] = await self.get_debug_embeds(active_list, active_count, total_list, total_count)
            embed_list.extend(debug_embeds)

        await interaction.response.send_message(embeds = embed_list)

    @ticketcount.error
    async def ticketcount_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client:commands.Bot) -> None:
    await client.add_cog(TicketCount(client))