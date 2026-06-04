from discord.ext import commands
from discord import app_commands
from typing import Literal
import discord
import json
from core.config import get_data
from core.database import execute
from core.decorators import task
from core.loggers import log_commands, log_tasks
from domain.ticket_system import TicketSystem
from ui.views.paginator import Paginator

class TicketsSend(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @app_commands.guild_only() 
    @app_commands.command(name = "send-tickets", description = "Sends a message prompt.")
    @app_commands.describe(option = "The message that you'd wish to send")
    async def send_tickets(self, interaction: discord.Interaction, option: Literal["Tickets"], channel: discord.TextChannel = None) -> None:
        await self.send_tickets_command(interaction, option, channel if channel else interaction.channel)

    @task("SendTickets Command", True)
    async def send_tickets_command(self, interaction: discord.Interaction, option: str, channel: discord.TextChannel) -> None:
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
        await self.request_tickets(interaction, Button)
    
    @task("Get Data", False)
    async def get_data(self, user_id: int):
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
        paginate = Paginator()
        paginate.title = f"{interaction.user.name}'s Tickets"
        paginate.sep = 5
        paginate.data = data
        await paginate.send(interaction)

    @task("Request Tickets", False)
    async def request_tickets(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await interaction.response.send_message(content = "...", ephemeral = True)

        data: list[str] = await self.get_data(interaction.user.id)
        await self.paginate_send(interaction, data)

        log_tasks.info(f"Sent the {Button.emoji} button to {interaction.user} ({interaction.user.id})")


class TicketsView(discord.ui.View):
    def __init__(self) -> None:
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
        await self.ticket_manager.new_ticket(interaction, self)


class TicketsView2(discord.ui.View):
    def __init__(self) -> None:
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
        await self.ticket_manager.new_ticket(interaction, self)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketsSend(client))