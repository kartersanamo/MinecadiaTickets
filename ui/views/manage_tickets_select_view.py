import discord

from core.errors.exceptions import UI_CALLBACK_ERRORS
from core.loggers import log_commands


class ManageTicketsSelect(discord.ui.Select):
    def __init__(self, ticket_info, ticket_category) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        labels = list(self.ticket_info.get(self.ticket_category).keys())
        options = [discord.SelectOption(label=label) for label in labels]
        super().__init__(placeholder="Select a ticket type to manage...", options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            from ui.views.manage_type_view import ManageTypeView

            ticket = self.values[0]
            await interaction.response.defer()
            view = ManageTypeView(self.ticket_info, self.ticket_category, ticket)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error(
                "%s (%s) has failed to select a ticket type in %s %s",
                interaction.user,
                interaction.user.id,
                self.ticket_category,
                e,
            )
