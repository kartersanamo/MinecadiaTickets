import discord
import json
from core.config import ConfigManager
from core.loggers import log_commands


class ManageCategoriesView(discord.ui.View):
    def __init__(self, ticket_info) -> None:
        super().__init__(timeout = None)
        self.ticket_info = ticket_info
        self.add_item(ManageCategoriesSelect(self.ticket_info))
    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await get_info()
            main_menu_embed = discord.Embed(title = "Main Menu",
                                color = discord.Color.from_str(ConfigManager.get('EMBED_COLOR')),
                                description = "Select Category")
            for ticket_cat in list(self.ticket_info.keys()):
                val = ""
                for ticket_type in list(self.ticket_info.get(ticket_cat).keys()):
                    val += f"\t `»` {ticket_type}\n"
                main_menu_embed.add_field(name = ticket_cat, value = val)
            await interaction.edit_original_response(embed = main_menu_embed, content = None)
        except Exception as e:
            log_commands.error(f"Failed to update the embed {e}")

    @discord.ui.button(label = "Toggle All Tickets", style = discord.ButtonStyle.red, custom_id = "toggle_all_tickets", row = 0, disabled = False)
    async def toggle_all_tickets(self, interaction: discord.Interaction, Button: discord.ui.Button):
        try:
            await interaction.response.defer()
            with open('assets/tickets.json', 'r+') as file:
                data = json.load(file)
                data['TOGGLE_STATUS'] = 'Disabled' if data['TOGGLE_STATUS'] == 'Enabled' else 'Enabled'
                file.seek(0)
                json.dump(data, file, indent=3)
                file.truncate()
            log_commands.info(f"{interaction.user} ({interaction.user.id}) has toggled all tickets to {data['TOGGLE_STATUS']}")
            await interaction.followup.send(content = f"`✅` Successfully toggled all tickets to `{data['TOGGLE_STATUS']}`", ephemeral = True)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to toggle all tickets {e}")
