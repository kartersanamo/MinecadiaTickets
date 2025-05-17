from Assets.functions import get_data, execute, log_commands, task
from Assets.classes import Paginator
from discord.ext import commands
from discord import app_commands
import discord


data = get_data()


@task("Is Admin", False)
async def is_admin(interaction: discord.Interaction) -> bool:
    """
    Checks if the user associated with the interaction is an admin.

    Parameters:
    interaction (discord.Interaction): The interaction object representing the context of the command.

    Returns:
    bool: True if the user is an admin, False otherwise.
    """
    return any(role.id in data["ADMIN_ROLES"] for role in interaction.user.roles)

@task("Is Management", False)
async def is_management(interaction: discord.Interaction) -> bool:
    """
    Checks if the user associated with the interaction has the management role.

    Parameters:
    interaction (discord.Interaction): The interaction object representing the context of the command.
        This object contains information about the user, channel, and guild associated with the command.

    Returns:
    bool: True if the user is a member of the management role, False otherwise.
        The management role is determined by the 'ADMINISTRATOR_PERMS_ROLE_ID' in the 'ROLE_IDS' dictionary.
    """
    star_role: discord.Role = interaction.guild.get_role(data['ROLE_IDS']['ADMINISTRATOR_PERMS_ROLE_ID'])
    return star_role in interaction.user.roles

@task("Get Data List", False)
async def get_data_list(closed_by: str, user: discord.Member, interaction: discord.Interaction, option: str) -> tuple[list[str], str]:
    """
    Retrieves a list of tickets based on the provided parameters and formats them for display.

    Parameters:
    closed_by (str): A string indicating whether the tickets are to be filtered by the user who closed them.
        If not empty, the function will retrieve tickets closed by the specified user.
    user (discord.Member): The Discord member object representing the user whose tickets are to be retrieved.
    interaction (discord.Interaction): The interaction object representing the context of the command.
    option (str): A string indicating the sorting option for the tickets.
        It can be either 'Opened At' or 'Closed At'.

    Returns:
    tuple[list[str], str]: A tuple containing two elements:
        - A list of formatted strings representing the tickets.
        - A string representing the title of the ticket list.
    """
    sql: str = 'opened_at' if option == 'Opened At' else 'closed_at'
    title: str = f"{user}'s Tickets Closed" if closed_by else f"{user}'s Tickets"
    rows: list[dict] = execute(f"SELECT name, type, transcript, reason, privated, closed_by, {sql} FROM tickets WHERE closed_by = '{user.id}' AND active = 'False' ORDER BY {sql} DESC") if closed_by else execute(f"SELECT name, type, transcript, reason, privated, closed_by, {sql} FROM tickets WHERE ownerID = '{user.id}' AND active = 'False' ORDER BY {sql} DESC")
    admin: bool = await is_admin(interaction)
    management: bool = await is_management(interaction)
    
    def format_timestamp(value: str) -> str:
        try:
            timestamp = float(value)
            return f"<t:{int(timestamp)}:f>"
        except ValueError:
            return value
    
    data: list[str] = [
        (
            f" `📕` **Ticket:** {row['name']} ({row['type']})\n" if row['privated'] == 'Admin' else
            f" `📘` **Ticket:** {row['name']} ({row['type']})\n" if row['privated'] == 'Management' else
            f" `📖` **Ticket:** {row['name']} ({row['type']})\n"
        ) + (
            f" **Transcript:** Privated Ticket\n" if row['privated'] == 'Admin' and not admin else
            " **Transcript:** Management Ticket\n" if row['privated'] == 'Management' and not management else
            f" **Transcript:** [Ticket Transcript]({row['transcript']})\n"
        ) + (
            f" **{option}:** {format_timestamp(row[sql])}\n"
        ) + (
            " **Closure Reason:** Hidden\n" if row['privated'] == 'Admin' and not admin or row['privated'] == 'Management' and not management else f" **Closure Reason:** {row['reason']}\n"
        ) + (
            f" **Closed By:** <@{row['closed_by']}>\n"
        )
        for row in rows
    ]
    return data if data else ["No data found."], title


class TicketLogs(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client

    @task("Ticket Logs Command", True)
    async def ticket_logs_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function is responsible for handling the ticket logs command. It retrieves the relevant data,
        formats it, and sends it to the user in a paginated manner.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the context of the command.
            This object contains information about the user, channel, and guild associated with the command.
        user (discord.Member): The Discord member object representing the user whose tickets are to be retrieved.

        Returns:
        None: This function does not return any value. It sends a response to the Discord interaction.
        """
        await interaction.response.defer()
        data = await get_data_list(False, user, interaction, 'Opened At')
        paginate = Paginator()
        paginate.add_item(ViewTicketsSelect('Opened At', user, interaction))
        paginate.add_item(Selection(False, user, interaction))
        paginate.title = data[1]
        paginate.sorted = " | Opened At | Opened By"
        paginate.data = data[0]
        paginate.sep = 5
        await paginate.send(interaction)

    @app_commands.guild_only()
    @app_commands.command(name = "ticket-logs", description = "Shows the previous tickets from a user")
    @app_commands.describe(user = "The user to lookup")
    async def ticketlogs(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function is responsible for handling the ticket logs command.
        It sends a request to retrieve the relevant data for a specific user, formats it, and sends it to the user in a paginated manner.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the context of the command.
            This object contains information about the user, channel, and guild associated with the command.
        user (discord.Member): The Discord member object representing the user whose tickets are to be retrieved.

        Returns:
        None: This function does not return any value. It sends a response to the Discord interaction.
        """
        await self.ticket_logs_command(interaction, user)

    @ticketlogs.error
    async def ticketlogs_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content=error, ephemeral=True) if interaction.response.is_done() else await interaction.response.send_message(content=error, ephemeral=True)


class Selection(discord.ui.Select):
    def __init__(self, closed_by, user, interaction):
        self.closed_by: str = closed_by
        self.user: discord.Member = user
        self.interaction: discord.Interaction = interaction
        super().__init__(
            placeholder = "Filter By...", 
            custom_id = "selection_ticket_logs", 
            options = [
                discord.SelectOption(label = "Opened At"), 
                discord.SelectOption(label = "Closed At")
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        """
        Handles the callback event for the ViewTicketsSelect class.
        This method is responsible for processing the user's selection, retrieving relevant data,
        formatting it, and sending it to the user in a paginated manner.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the context of the command.
            This object contains information about the user, channel, and guild associated with the command.

        Returns:
        None: This method does not return any value. It sends a response to the Discord interaction.
        """
        await interaction.response.defer()
        choice = self.values[0]
        data = await get_data_list(self.closed_by, self.user, self.interaction, choice)
        paginate = Paginator()
        paginate.add_item(ViewTicketsSelect(choice, self.user, interaction))
        paginate.add_item(Selection(self.closed_by, self.user, interaction))
        paginate.title = data[1]
        paginate.sorted = f" | {self.closed_by} | {choice}"
        paginate.data = data[0]
        paginate.sep = 5
        await paginate.send(interaction)


class ViewTicketsSelect(discord.ui.Select):
    def __init__(self, option, user, interaction):
        self.option: str = option
        self.user: discord.Member = user
        self.interaction: discord.Interaction = interaction
        super().__init__(
            placeholder = "View Tickets...", 
            custom_id = "view_tickets_select", 
            options = [
                discord.SelectOption(label = f"Opened By {self.user.name}"), 
                discord.SelectOption(label = f"Closed By {self.user.name}")
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        """
        Handles the callback event for the ViewTicketsSelect class.
        This method is responsible for processing the user's selection, retrieving relevant data,
        formatting it, and sending it to the user in a paginated manner.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the context of the command.
            This object contains information about the user, channel, and guild associated with the command.

        Returns:
        None: This method does not return any value. It sends a response to the Discord interaction.
        """
        await interaction.response.defer()
        choice = ' '.join(self.values[0].split(' ')[:2])
        closed_by: bool = True if "Closed By" in choice else False
        data = await get_data_list(closed_by, self.user, self.interaction, self.option)
        paginate = Paginator()
        paginate.add_item(ViewTicketsSelect(self.option, self.user, interaction))
        paginate.add_item(Selection(choice, self.user, interaction))
        paginate.title = data[1]
        paginate.sorted = f" | {self.option} | {choice}"
        paginate.data = data[0]
        paginate.sep = 5
        await paginate.send(interaction)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketLogs(client))