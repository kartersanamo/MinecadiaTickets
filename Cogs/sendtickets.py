from Assets.functions import get_data, execute, log_commands, log_tasks, task
from Assets.classes import Paginator, TicketSystem
from discord.ext import commands
from discord import app_commands
from typing import Literal
import discord
import json

class TicketsSend(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @app_commands.guild_only() 
    @app_commands.command(name = "send-tickets", description = "Sends a message prompt.")
    @app_commands.describe(option = "The message that you'd wish to send")
    async def send_tickets(self, interaction: discord.Interaction, option: Literal["Tickets"], channel: discord.TextChannel = None) -> None:
        """
        This function sends a message prompt to a specified channe.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the command.
        option (Literal["Tickets"]): The type of message prompt to send. Currently only supports "Tickets".
        channel (discord.TextChannel, optional): The channel to send the message prompt to. If not provided, the message will be sent to the channel where the command was invoked.

        Returns:
        None
        """
        await self.send_tickets_command(interaction, option, channel if channel else interaction.channel)

    @task("SendTickets Command", True)
    async def send_tickets_command(self, interaction: discord.Interaction, option: str, channel: discord.TextChannel) -> None:
        """
        This function sends a message prompt to a specified channel with ticket-related information as that is the only current option.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the command.
        option (str): The type of message prompt to send. Currently only supports "Tickets".
        channel (discord.TextChannel): The channel to send the message prompt to. If not provided, the message will be sent to the channel where the command was invoked.

        Returns:
        None
        """
        None if interaction.response.is_done() else await interaction.response.send_message(content = "`🔃` Sending your message...", ephemeral = True)

        embeds = {
            "Tickets": [
                {
                    "embed": discord.Embed(
                        color = discord.Color.from_str(self.data["EMBED_COLOR"]), 
                        description = ("**Select a category that best represents your ticket reasoning**:\n\n"
                                       ""
                                       "**-** Be sure to be as specific and detailed as possible in your ticket.\n"
                                       "**-** Any visual evidence should be uploaded to [Imgur](https://imgur.com/upload) & [YouTube](https://www.youtube.com/).\n"
                                       "**-** A staff member will be with you as soon as possible.")
                    ),
                    "view": TicketsView(),
                    "image": "https://i.imgur.com/k93vtvB.png"
                },
                {
                    "embed": None,
                    "view": TicketsView2(),
                    "image": None
                },
                {
                    "embed": discord.Embed(
                        color = discord.Color.from_str(self.data["EMBED_COLOR"]),
                        description = "**Want to see your previous tickets? Click the envelope down below!**"
                    ),
                    "view": TicketLogs(),
                    "image": None
                }
            ]
        }
        chosen_message: list[dict] = embeds.get(option, [])
        for message in chosen_message:
            embed = message['embed']
            if message['image']:
                embed.set_image(url = message['image'])
            await channel.send(embed = embed, view = message['view'])
        
        await interaction.edit_original_response(content = "`✅` Successfully sent your message prompt!")

    @send_tickets.error
    async def send_tickets_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


class TicketLogs(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.data: dict = get_data()

    @discord.ui.button(emoji = "📨", style = discord.ButtonStyle.grey, custom_id = "request_tickets_button")
    async def request(self, interaction: discord.Interaction, Button: discord.ui.Button):
        """
        This function handles the request button click event in the TicketLogs view.
        It sends a message with the user's previous tickets to the interaction channel.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the button click.
        Button (discord.ui.Button): The button object that was clicked.

        Returns:
        None
        """
        await self.request_tickets(interaction, Button)
    
    @task("Get Data", False)
    async def get_data(self, user_id: int):
        """
        Retrieves and formats the user's closed tickets data.

        Parameters:
        user_id (int): The unique identifier of the user whose tickets data is to be retrieved.

        Returns:
        list[str]: A list of formatted strings representing the user's closed tickets. Each string contains
        information such as ticket name, type, transcript URL, creation date, and closure reason. If no data is found,
        a list containing a single string "No data found." is returned.
        """
        rows = execute(f"SELECT opened_at, name, type, transcript, reason FROM tickets WHERE ownerID = '{user_id}' AND active = 'False' ORDER BY opened_at")
        data: list = []

        for row in rows:
            opened_at = int(float(row['opened_at']))
            ticket_info = (
                f"`📖` **Ticket:** {row['name']} ({row['type']})\n"
                f" **Transcript:** [Ticket Transcript]({row['transcript']})\n"
                f" **Created At:** <t:{opened_at}:f>\n"
                f" **Closure Reason:** {row['reason']}\n"
            )
            data.append(ticket_info)
        if not data:
            data = ["No data found."]
        else:
            data.reverse()
        
        return data

    @task("Paingate Send", False)
    async def paginate_send(self, interaction: discord.Interaction, data: list[str]):
        """
        This function sends paginated messages containing the user's closed tickets to the interaction channel.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the function.
        data (list[str]): A list of formatted strings representing the user's closed tickets. Each string contains
        information such as ticket name, type, transcript URL, creation date, and closure reason.

        Returns:
        None
        """
        paginate = Paginator()
        paginate.title = f"{interaction.user.name}'s Tickets"
        paginate.sep = 5
        paginate.data = data
        await paginate.send(interaction)

    @task("Request Tickets", False)
    async def request_tickets(self, interaction: discord.Interaction, Button: discord.ui.Button):
        """
        This function handles the request button click event in the TicketLogs view.
        It sends a message with the user's previous tickets to the interaction channel.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the button click.
        Button (discord.ui.Button): The button object that was clicked.

        Returns:
        None
        """
        await interaction.response.send_message(content = "...", ephemeral = True)

        data: list[str] = await self.get_data(interaction.user.id)
        await self.paginate_send(interaction, data)

        log_tasks.info(f"Sent the {Button.emoji} button to {interaction.user} ({interaction.user.id})")


class TicketsView(discord.ui.View):
    def __init__(self) -> None:
        """
        Initializes the TicketsView class.

        This class represents a Discord UI view for selecting ticket categories. It loads ticket categories from a JSON file,
        creates Discord select options for each category, and adds them to the view.

        Parameters:
        None

        Returns:
        None
        """
        super().__init__(timeout = None)
        self.data = get_data()
        self.tickets: dict 
        self.ticket_manager: TicketSystem = TicketSystem()

        with open('Assets/tickets.json', 'r') as file:
            tickets = json.load(file)
            del tickets['TOGGLE_STATUS']
            self.tickets = tickets 

        for category_name, category_info in list(self.tickets.items())[:5]:
            select_options = [
                discord.SelectOption(
                    label = option_name,
                    emoji = option_info['Emoji'],
                    description = option_info['Description']
                )
                for option_name, option_info in category_info.items()
                if option_name != "Role"
            ]

            select = discord.ui.Select(
                custom_id = category_name,
                placeholder = category_name,
                options = select_options
            )
            select.callback = self.handle_selection
            self.add_item(select)

    async def handle_selection(self, interaction: discord.Interaction):
        """
        This function handles the selection event in the TicketsView and TicketsView2 views.
        It creates a new ticket based on the selected category and sends it to the ticket manager.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the selection event.

        Returns:
        None
        """
        await self.ticket_manager.new_ticket(interaction, self)


class TicketsView2(discord.ui.View):
    def __init__(self) -> None:
        """
        Initializes the TicketsView2 class.

        This class represents a Discord UI view for selecting ticket categories. It loads ticket categories from a JSON file,
        creates Discord select options for each category, and adds them to the view. The categories are divided into two views
        for better user experience.

        Parameters:
        None

        Returns:
        None
        """
        super().__init__(timeout = None)
        self.data = get_data()
        self.tickets: dict 
        self.ticket_manager: TicketSystem = TicketSystem()

        with open('Assets/tickets.json', 'r') as file:
            tickets = json.load(file)
            del tickets['TOGGLE_STATUS']
            self.tickets = tickets 

        for category_name, category_info in list(self.tickets.items())[5:]:
            select_options = [
                discord.SelectOption(
                    label = option_name,
                    emoji = option_info['Emoji'],
                    description = option_info['Description']
                )
                for option_name, option_info in category_info.items()
                if option_name != "Role"
            ]

            select = discord.ui.Select(
                custom_id = category_name,
                placeholder = category_name,
                options = select_options
            )
            select.callback = self.handle_selection
            self.add_item(select)

    async def handle_selection(self, interaction: discord.Interaction):
        """
        This function handles the selection event in the TicketsView and TicketsView2 views.
        It creates a new ticket based on the selected category and sends it to the ticket manager.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the selection event.
            This object contains information about the interaction, such as the user who triggered it,
            the channel where the interaction occurred, and the specific command or button that was clicked.

        Returns:
        None
        """
        await self.ticket_manager.new_ticket(interaction, self)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketsSend(client))