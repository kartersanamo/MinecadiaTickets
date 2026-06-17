from typing import Any
import discord

from core.loggers import log_commands
class ManageCategoriesSelect(discord.ui.Select):
    def __init__(self, ticket_info) -> None:
        self.ticket_info = ticket_info
        labels = [category_name for category_name in list[Any](self.ticket_info.keys())]
        options = [discord.SelectOption(label = label) for label in labels]
        super().__init__(placeholder = "Select a ticket category to manage...", options = options)
    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            from ui.views.manage_tickets_view import ManageTicketsView

            category = self.values[0]
            await interaction.response.defer()
            view = ManageTicketsView(self.ticket_info, category)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to select a ticket category {e}")
