#from cogs.sendtickets import send_tickets_command
from discord.ext import commands
from discord import app_commands
import discord
import json
from core.config import get_data
from core.loggers import log_commands


class ManageTicketsSelect(discord.ui.Select):
    def __init__(self, ticket_info, ticket_category) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        labels = [category_name for category_name in list(self.ticket_info.get(self.ticket_category).keys())]
        options = [discord.SelectOption(label = label) for label in labels]
        super().__init__(placeholder = "Select a ticket type to manage...", options = options)
        self.data = get_data()

    async def callback(self, interaction: discord.Interaction):
        try:
            ticket = self.values[0]
            await interaction.response.defer()
            view = ManageTypeView(self.ticket_info, self.ticket_category, ticket)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to select a ticket type in {self.ticket_category} {e}")
