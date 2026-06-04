#from cogs.sendtickets import send_tickets_command
from discord.ext import commands
from discord import app_commands
import discord
import json
from core.config import get_data
from core.loggers import log_commands


class ManageTicketsView(discord.ui.View):
    def __init__(self, ticket_info, category) -> None:
        super().__init__(timeout = None)
        self.ticket_info = ticket_info
        self.category = category
        self.add_item(ManageTicketsSelect(self.ticket_info, category))
        self.data = get_data()
        self.status_to_emoji = {
            "Enabled": "✅",
            "Disabled": "❌"
        }

    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await get_info()
            category_info = self.ticket_info.get(self.category)
            category_embed = discord.Embed(title = f"Category Editor",
                                        color = discord.Color.from_str(self.data['EMBED_COLOR']),
                                        description = self.category)
            for ticket_type in list(self.ticket_info.get(self.category).keys()):
                ticket_info = category_info.get(ticket_type)
                category_embed.add_field(name = f"`{self.status_to_emoji.get(ticket_info.get('Status'))}` {ticket_type}", value = f"`»` {ticket_info.get('Description')}\n`»` {ticket_info.get('Status')}")
            await interaction.edit_original_response(embed = category_embed)
        except Exception as e:
            log_commands.error(f"Failed to update the embed {e}")

    @discord.ui.button(label = "|<", style = discord.ButtonStyle.red, custom_id = "go_back_category", row = 0, disabled = False)
    async def go_back_category(self, interaction: discord.Interaction, Button: discord.ui.Button):
        try:
            await interaction.response.defer()
            view = ManageCategoriesView(self.ticket_info)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to go back {e}")
    
    @discord.ui.button(label = "Toggle Category", style = discord.ButtonStyle.grey, custom_id = "toggle_category", row = 0, disabled = False)
    async def toggle_category(self, interaction: discord.Interaction, Button: discord.ui.Button):
        try:
            await interaction.response.defer()
            output = f"Successfully toggled the following tickets...\n"
            with open("assets/tickets.json", "r+") as file:
                info = json.load(file)
                for ticket_type in list(info.get(self.category).keys()):
                    status = info.get(self.category).get(ticket_type)['Status']
                    new_status = 'Enabled' if status == 'Disabled' else 'Disabled'
                    info.get(self.category).get(ticket_type)['Status'] = new_status
                    output += f"\n`{self.status_to_emoji.get(new_status)}` **{ticket_type}** is now {new_status}"
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            view = ManageTicketsView(self.ticket_info, self.category)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
            await interaction.followup.send(content = output, ephemeral = True)
            await update_msg(interaction)
            log_commands.info(f"{interaction.user} ({interaction.user.id}) has toggled the {self.category} category to {new_status}")
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to toggle {self.category} {e}")
