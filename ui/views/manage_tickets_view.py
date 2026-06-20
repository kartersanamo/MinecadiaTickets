import json

import discord

from core.config import ConfigManager
from core.errors.exceptions import UI_CALLBACK_ERRORS
from core.loggers import log_commands
from ui.views.manage_tickets_support import ManageTicketsSupport


class ManageTicketsView(discord.ui.View):
    def __init__(self, ticket_info, category) -> None:
        super().__init__(timeout=None)
        self.ticket_info = ticket_info
        self.category = category
        from ui.views.manage_tickets_select_view import ManageTicketsSelect

        self.add_item(ManageTicketsSelect(self.ticket_info, category))
        self.status_to_emoji = {"Enabled": "✅", "Disabled": "❌"}

    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await ConfigManager.reload_tickets()
            category_info = self.ticket_info.get(self.category, {})
            category_embed = discord.Embed(
                title="Category Editor",
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
                description=self.category,
            )
            for ticket_type in list(self.ticket_info.get(self.category, {}).keys()):
                ticket_info = category_info.get(ticket_type, {})
                category_embed.add_field(
                    name=f"`{self.status_to_emoji.get(ticket_info.get('Status'))}` {ticket_type}",
                    value=f"`»` {ticket_info.get('Description')}\n`»` {ticket_info.get('Status')}",
                )
            await interaction.edit_original_response(embed=category_embed)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("Failed to update the embed %s", e)

    @staticmethod
    async def update_msg(interaction: discord.Interaction) -> None:
        await ManageTicketsSupport.update_msg(interaction)

    @discord.ui.button(label="|<", style=discord.ButtonStyle.red, custom_id="go_back_category", row=0, disabled=False)
    async def go_back_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from ui.views.manage_categories_view import ManageCategoriesView

            await interaction.response.defer()
            view = ManageCategoriesView(self.ticket_info)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("%s (%s) has failed to go back %s", interaction.user, interaction.user.id, e)

    @discord.ui.button(
        label="Toggle Category", style=discord.ButtonStyle.grey, custom_id="toggle_category", row=0, disabled=False
    )
    async def toggle_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            output = "Successfully toggled the following tickets...\n"
            with open("assets/tickets.json", "r+", encoding="utf-8") as file:
                info = json.load(file)
                for ticket_type in list(info.get(self.category).keys()):
                    status = info.get(self.category).get(ticket_type)["Status"]
                    new_status = "Enabled" if status == "Disabled" else "Disabled"
                    info.get(self.category).get(ticket_type)["Status"] = new_status
                    output += f"\n`{self.status_to_emoji.get(new_status)}` **{ticket_type}** is now {new_status}"
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            view = ManageTicketsView(self.ticket_info, self.category)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
            await interaction.followup.send(content=output, ephemeral=True)
            await ManageTicketsSupport.update_msg(interaction)
            log_commands.info(
                "%s (%s) has toggled the %s category to %s",
                interaction.user,
                interaction.user.id,
                self.category,
                info.get(self.category, {}).get("Status", "None"),
            )
        except UI_CALLBACK_ERRORS as e:
            log_commands.error(
                "%s (%s) has failed to toggle %s %s", interaction.user, interaction.user.id, self.category, e
            )
