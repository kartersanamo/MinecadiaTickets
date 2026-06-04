import discord
from core.config import get_data
from core.database import execute
from core.decorators import task
from core.loggers import log_tasks
from ui.views.paginator import Paginator


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
