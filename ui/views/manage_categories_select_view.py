import discord

from core.errors.exceptions import UI_CALLBACK_ERRORS
from core.loggers import log_commands


class ManageCategoriesSelect(discord.ui.Select):
    def __init__(self, ticket_info) -> None:
        self.ticket_info = ticket_info
        labels = list(self.ticket_info.keys())
        options = [discord.SelectOption(label=label) for label in labels]
        super().__init__(placeholder="Select a ticket category to manage...", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            category = self.values[0]
            await interaction.response.defer()
            view = ManageTicketsView(self.ticket_info, category)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error(
                "%s (%s) has failed to select a ticket category %s", interaction.user, interaction.user.id, e
            )


from ui.views.manage_tickets_view import ManageTicketsView
