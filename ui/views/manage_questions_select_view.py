#from cogs.sendtickets import send_tickets_command
from discord.ext import commands
from discord import app_commands
import discord
import json
from core.config import get_data
from core.loggers import log_commands


class ManageQuestionsSelect(discord.ui.Select):
    def __init__(self, ticket_info, ticket_category, ticket) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        self.ticket = ticket
        labels = [question.get('Label', 'None') for question in list(self.ticket_info.get(self.ticket_category, {self.ticket_category: {self.ticket: {"Questions": [{'Label': 'None'}]}}}).get(self.ticket, {self.ticket: {"Questions": [{'Label': 'None'}]}}).get('Questions', [{'Label': 'None'}]))]
        options = [discord.SelectOption(label = label) for label in labels]
        super().__init__(placeholder = "Select a question to manage...", options = options)
        self.data = get_data()
    
    async def callback(self, interaction: discord.Interaction):
        try:
            question = self.values[0]
            await interaction.response.defer()
            view = ManageQuestionView(self.ticket_info, self.ticket_category, self.ticket, question)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to select a question to manage in {self.ticket_category} {self.ticket} {e}")
