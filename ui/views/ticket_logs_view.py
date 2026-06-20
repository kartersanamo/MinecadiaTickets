import discord

from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.loggers import log_tasks
from ui.views.paginator import Paginator


class TicketLogs(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(emoji="📨", style=discord.ButtonStyle.grey, custom_id="request_tickets_button")
    async def request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.request_tickets(interaction, button)

    @TaskDecorator.task("Get Data", False)
    async def get_data(self, user_id: int):
        rows = DatabasePool.execute(
            "SELECT opened_at, name, type, transcript, reason FROM tickets WHERE owner_id = %s AND is_active = 0 ORDER BY opened_at",
            (user_id,),
        )
        data: list = []

        for row in rows:
            opened_at = int(float(row["opened_at"]))
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

    @TaskDecorator.task("Paingate Send", False)
    async def paginate_send(self, interaction: discord.Interaction, data: list[str]):
        paginate = Paginator()
        paginate.title = f"{interaction.user.name}'s Tickets"
        paginate.sep = 5
        paginate.data = data
        await paginate.send(interaction)

    @TaskDecorator.task("Request Tickets", False)
    async def request_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="...", ephemeral=True)

        data: list[str] = await self.get_data(interaction.user.id)
        await self.paginate_send(interaction, data)

        log_tasks.info("Sent the %s button to %s (%s)", Button.emoji, interaction.user, interaction.user.id)
