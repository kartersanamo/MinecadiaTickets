#from cogs.sendtickets import send_tickets_command
from discord.ext import commands
from discord import app_commands
import discord
from core.config import get_data
from core.loggers import log_commands
from ui.views.manage_categories_view import ManageCategoriesView

class ManageTickets(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.data = get_data()

    @app_commands.guild_only()
    @app_commands.command(name = "manage-tickets", description = "Manages the ticket types")
    async def manage_tickets(self, interaction: discord.Interaction):
        await interaction.response.send_message(content = "Fetching the manage tickets menu...")
        ticket_info = await get_info()
        view = ManageCategoriesView(ticket_info)
        await view.update_embed(interaction)
        await interaction.edit_original_response(view = view)

    @manage_tickets.error
    async def manage_tickets_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(ManageTickets(client))