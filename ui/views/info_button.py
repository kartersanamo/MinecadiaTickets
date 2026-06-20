import discord

from core.errors.exceptions import UI_CALLBACK_ERRORS
from core.loggers import log_tasks
from ui.modals.questions import Questions


class InfoButton(discord.ui.View):
    def __init__(self, ticket_type: str, ticket_info) -> None:
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        self.ticket_info = ticket_info

    @discord.ui.button(
        label="Enter Information",
        style=discord.ButtonStyle.grey,
        custom_id="enter_information",
    )
    async def enter_information_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(Questions(self.ticket_type, self.ticket_info))
            log_tasks.info("Sent the Questions modal to %s (%s)", interaction.user, interaction.user.id)
        except UI_CALLBACK_ERRORS as e:
            log_tasks.error(
                "Failed to send the Questions modal to %s (%s) %s",
                interaction.user,
                interaction.user.id,
                e,
            )
