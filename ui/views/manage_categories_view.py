import json
from typing import Any

import discord

from core.config import ConfigManager
from core.errors.exceptions import UI_CALLBACK_ERRORS
from core.loggers import log_commands


class ManageCategoriesView(discord.ui.View):
    def __init__(self, ticket_info) -> None:
        super().__init__(timeout=None)
        self.ticket_info = ticket_info
        from ui.views.manage_categories_select_view import ManageCategoriesSelect

        self.add_item(ManageCategoriesSelect(self.ticket_info))

    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await ConfigManager.reload_tickets()
            main_menu_embed = discord.Embed(
                title="Main Menu",
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
                description="Select Category",
            )
            for ticket_cat in list[Any](self.ticket_info.keys()):
                ticket_types = self.ticket_info.get(ticket_cat, {})
                val = "".join(f"\t `»` {ticket_type}\n" for ticket_type in ticket_types)
                main_menu_embed.add_field(name=ticket_cat, value=val)
            await interaction.edit_original_response(embed=main_menu_embed, content=None)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("Failed to update the embed %s", e)

    @discord.ui.button(
        label="Toggle All Tickets", style=discord.ButtonStyle.red, custom_id="toggle_all_tickets", row=0, disabled=False
    )
    async def toggle_all_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            with open("assets/tickets.json", "r+", encoding="utf-8") as file:
                data = json.load(file)
                data["TOGGLE_STATUS"] = "Disabled" if data["TOGGLE_STATUS"] == "Enabled" else "Enabled"
                file.seek(0)
                json.dump(data, file, indent=3)
                file.truncate()
            log_commands.info(
                "%s (%s) has toggled all tickets to %s",
                interaction.user,
                interaction.user.id,
                data["TOGGLE_STATUS"],
            )
            await interaction.followup.send(
                content=f"`✅` Successfully toggled all tickets to `{data['TOGGLE_STATUS']}`", ephemeral=True
            )
        except UI_CALLBACK_ERRORS as e:
            log_commands.error(
                "%s (%s) has failed to toggle all tickets %s", interaction.user, interaction.user.id, e
            )
