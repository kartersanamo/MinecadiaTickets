import json
from typing import Any

import discord

from core.config import ConfigManager
from core.errors.exceptions import UI_CALLBACK_ERRORS
from core.loggers import log_commands
from services.ticket_access_service import TicketAccessService
from ui.views.manage_tickets_support import ManageTicketsSupport


class ManageTypeView(discord.ui.View):
    def __init__(self, ticket_info, ticket_category, ticket) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        self.ticket = ticket
        super().__init__(timeout=None)
        self.add_item(ManageQuestionsSelect(self.ticket_info, self.ticket_category, self.ticket))
        self.mapping = {
            "Name": {
                "Description": (
                    "*This is the name of the ticket type, and will be displayed as the name on the drop down item.*"
                ),
                "Image": "https://i.imgur.com/EEcY2HU.png",
            },
            "Emoji": {
                "Description": (
                    "*This emoji will appear next to the ticket type's name after clicking on the ticket category.*"
                ),
                "Image": "https://i.imgur.com/vrgPt9q.png",
            },
            "Description": {
                "Description": (
                    "*This value will be displayed on the line next to the emoji to describe the ticket type.*"
                ),
                "Image": "https://i.imgur.com/xAsHZjW.png",
            },
            "Message": {
                "Description": (
                    "*This is the message that will be displayed in the ticket once the user opens the ticket. "
                    "By default, the embed will show their name, the ticket type, and all of their questions/answers. "
                    "This 'message' (such as revive rules) will be displayed after their last answer. "
                    "After that will be a general message about staff support.*"
                ),
                "Image": "https://i.imgur.com/eD4qX3S.png",
            },
            "Roles": {
                "Description": (
                    "*These are the roles that can view the ticket channel when it is opened. By default, anyone "
                    "with the* `*` *role can view the channel,* `@everyone` *cannot view it, and* `@Staff Team` "
                    "*cannot view it. Any role in this list will be an addition to what was listed and will be able "
                    "to view it and send messages. These roles in this list should ALWAYS match the roles that can "
                    "view and send messages in the channel of the categories permissions. Otherwise, when moving to "
                    "this category, permissions will adopt the permissions of the category, not the ones in this "
                    "list.*\n \n"
                    "`SEND THE ROLE IDs OF EACH ROLE SEPERATED BY A SPACE. "
                    "ONE WRONG SPACE/CHARACTER AND IT WON'T WORK.`"
                ),
                "Image": "https://i.imgur.com/rTZ1k8H.png",
            },
            "Pings": {
                "Description": (
                    "*The pings represent a list of what roles will be pinged when the ticket is opened.*\n \n"
                    "`SEND THE ROLE IDs OF EACH ROLE SEPERATED BY A SPACE. "
                    "ONE WRONG SPACE/CHARACTER AND IT WON'T WORK.`"
                ),
                "Image": None,
            },
            "Users": {
                "Description": (
                    "*These are the user IDs that can view the ticket channel when it is opened. Use this instead of "
                    "roles for tickets that should only be visible to specific people. By default,* `@everyone` "
                    "*cannot view it,* `@Staff Team` *cannot view it, and only the ticket opener plus these users "
                    "can view it.\n \n"
                    "`SEND THE USER IDs OF EACH USER SEPERATED BY A SPACE. "
                    "ONE WRONG SPACE/CHARACTER AND IT WON'T WORK.`"
                ),
                "Image": None,
            },
            "Category": {
                "Description": (
                    "*This is the category that the ticket will be placed under when it is opened. Permissions for all "
                    "tickets opened under this category are based on the permissions of the category. So please, make "
                    "sure that the permissions are set up for that category first. For more information on how this "
                    "works, read the 'Roles' blurb.*\n \n"
                    "`SEND ONE SINGLE CATEGORY ID. ONE WRONG SPACE/CHARACTER AND IT WON'T WORK.`"
                ),
                "Image": None,
            },
        }

    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await ConfigManager.reload_tickets()
            guild = interaction.guild
            if guild is None:
                return
            cat_info = self.ticket_info.get(self.ticket_category, {})
            ticket_info = cat_info.get(self.ticket, {})
            category = guild.get_channel(ticket_info.get("Category", 0))
            category_string = (
                f"{category.mention} ({category.id})"
                if isinstance(category, discord.abc.GuildChannel)
                else "# None (0000000000000000)"
            )
            pings = [
                role.mention
                for role_id in ticket_info.get("Pings", [])
                if (role := guild.get_role(role_id)) is not None
            ]
            roles = [
                role.mention
                for role_id in ticket_info.get("Roles", [])
                if (role := guild.get_role(role_id)) is not None
            ]
            user_ids = TicketAccessService.resolve_user_ids(self.ticket, ticket_info)
            users = [f"<@{user_id}> ({user_id})" for user_id in user_ids]
            if not pings:
                pings = ["None"]
            if not roles:
                roles = ["None"]
            if not users:
                users = ["None"]
            if len(ticket_info.get("Message")) > 1000:
                message = (
                    f"```{ticket_info.get('Message')[:1000]}\n...```" if ticket_info.get("Message", None) else "None"
                )
            else:
                message = f"```{ticket_info.get('Message')}```" if ticket_info.get("Message", None) else "None"
            manage_type_embed = discord.Embed(
                title="Manage Ticket Type",
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
                description=self.ticket_category + " » " + self.ticket,
            )
            manage_type_embed.add_field(name="Status", value=ticket_info.get("Status", "None"))
            manage_type_embed.add_field(name="Emoji", value=ticket_info.get("Emoji", "None"))
            manage_type_embed.add_field(name="Description", value=ticket_info.get("Description", "None"))
            manage_type_embed.add_field(name="Category", value=category_string)
            manage_type_embed.add_field(name="Pings", value="".join(pings))
            manage_type_embed.add_field(name="Roles", value="".join(roles))
            manage_type_embed.add_field(name="Users", value="".join(users))
            manage_type_embed.add_field(name="Message", value=message)
            questions_embed = discord.Embed(
                title="Manage Ticket Questions",
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
                description=self.ticket_category + " » " + self.ticket,
            )
            for question in ticket_info.get("Questions", [{}]):
                questions_embed.add_field(
                    name=question.get("Label", "None"),
                    value=f"`»` {question.get('Placeholder', 'None')}\n `»` {question.get('Length', 'None')}",
                )
            await interaction.edit_original_response(embeds=[manage_type_embed, questions_embed])
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("Failed to update the embed %s", e)

    async def change_value(self, interaction: discord.Interaction, value):
        try:
            if interaction.guild is None:
                return
            guild = interaction.guild
            star_role = guild.get_role(ConfigManager.get("ROLE_IDS")["ADMINISTRATOR_PERMS_ROLE_ID"])
            if star_role is None:
                return await interaction.response.send_message(
                    content="Administrator permissions role not found!", ephemeral=True
                )
            if not isinstance(interaction.user, discord.Member) or not star_role in interaction.user.roles:
                return await interaction.response.send_message(content="You can't do this!", ephemeral=True)
            await interaction.response.defer()
            await self.update_embed(interaction)
            if (
                interaction.message is None
                or interaction.message.embeds is None
                or len(interaction.message.embeds) == 0
            ):
                return
            top_embed = interaction.message.embeds[0]
            if top_embed is None:
                return
            description, image = list[Any](self.mapping.get(value, {}).values())
            embed = discord.Embed(
                title=f"Enter the new {value.lower()} below",
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
                description=description,
            )
            embed.set_image(url=image)
            await interaction.message.edit(embeds=[top_embed, embed], view=None)

            def check(m, *, _guild: discord.Guild = guild):
                if value in ("Roles", "Pings"):
                    for role in m.content.split(" "):
                        try:
                            if _guild.get_role(int(role)) is None:
                                return False
                        except (ValueError, TypeError):
                            return False
                if value == "Users":
                    for user_id in m.content.split(" "):
                        if not user_id:
                            continue
                        try:
                            int(user_id)
                        except (ValueError, TypeError):
                            return False
                if value == "Category":
                    try:
                        if guild.get_channel(int(m.content)) is None:
                            return False
                    except (ValueError, TypeError):
                        return False
                if m.channel == interaction.channel and m.author == interaction.user:
                    return True
                return False

            new_value = await interaction.client.wait_for("message", check=check)
            new_value.content = "" if new_value.content == "None" else new_value.content
            with open("assets/tickets.json", "r+", encoding="utf-8") as file:
                info = json.load(file)
                if value in ["Message", "Description", "Emoji"]:
                    info[self.ticket_category][self.ticket][value] = new_value.content
                elif value == "Name":
                    info[self.ticket_category][new_value.content] = info[self.ticket_category].pop(self.ticket)
                    self.ticket = new_value.content
                elif value in ["Roles", "Pings"]:
                    info[self.ticket_category][self.ticket][value] = [
                        int(role) for role in new_value.content.split(" ")
                    ]
                elif value == "Users":
                    info[self.ticket_category][self.ticket][value] = [
                        int(user_id) for user_id in new_value.content.split(" ") if user_id
                    ]
                elif value == "Category":
                    info[self.ticket_category][self.ticket][value] = int(new_value.content)
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            await new_value.delete()
            view = ManageTypeView(self.ticket_info, self.ticket_category, self.ticket)
            await view.update_embed(interaction)
            await interaction.message.edit(view=view)
            await ManageTicketsSupport.update_msg(interaction)
            log_commands.info(
                "%s (%s) has changed %s to %s for %s %s",
                interaction.user,
                interaction.user.id,
                value,
                new_value,
                self.ticket_category,
                self.ticket,
            )
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("Failed to change the value of %s %s", value, e)

    @discord.ui.button(label="|<", style=discord.ButtonStyle.red, custom_id="go_back_type", row=0, disabled=False)
    async def go_back_type(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.defer()
            view = ManageTicketsView(self.ticket_info, self.ticket_category)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("%s (%s) has failed to go back %s", interaction.user, interaction.user.id, e)

    @discord.ui.button(
        label="Toggle Status", style=discord.ButtonStyle.grey, custom_id="toggle_status", row=0, disabled=False
    )
    async def toggle_status(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.defer()
            with open("assets/tickets.json", "r+", encoding="utf-8") as file:
                info = json.load(file)
                new_status = (
                    "Enabled" if info[self.ticket_category][self.ticket]["Status"] == "Disabled" else "Disabled"
                )
                info[self.ticket_category][self.ticket]["Status"] = new_status
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            view = ManageTypeView(self.ticket_info, self.ticket_category, self.ticket)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
            await ManageTicketsSupport.update_msg(interaction)
            await interaction.followup.send(content="Successfully toggled this ticket type.", ephemeral=True)
            log_commands.info(
                "%s (%s) has toggled %s %s ticket type to %s",
                interaction.user,
                interaction.user.id,
                self.ticket_category,
                self.ticket,
                new_status,
            )
        except UI_CALLBACK_ERRORS as e:
            log_commands.error(
                "%s (%s) has failed to toggle ticket type of %s %s %s",
                interaction.user,
                interaction.user.id,
                self.ticket_category,
                self.ticket,
                e,
            )

    @discord.ui.button(
        label="Change Name", style=discord.ButtonStyle.grey, custom_id="change_name", row=0, disabled=False
    )
    async def change_name(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Name")

    @discord.ui.button(
        label="Change Emoji", style=discord.ButtonStyle.grey, custom_id="change_emoji", row=0, disabled=False
    )
    async def change_emoji(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Emoji")

    @discord.ui.button(
        label="Change Description",
        style=discord.ButtonStyle.grey,
        custom_id="change_description",
        row=0,
        disabled=False,
    )
    async def change_description(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Description")

    @discord.ui.button(
        label="Change Category", style=discord.ButtonStyle.grey, custom_id="change_category", row=1, disabled=False
    )
    async def change_category(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Category")

    @discord.ui.button(
        label="Change Message", style=discord.ButtonStyle.grey, custom_id="change_message", row=1, disabled=False
    )
    async def change_message(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Message")

    @discord.ui.button(
        label="Change Roles", style=discord.ButtonStyle.grey, custom_id="change_roles", row=1, disabled=False
    )
    async def change_roles(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Roles")

    @discord.ui.button(
        label="Change Pings", style=discord.ButtonStyle.grey, custom_id="change_pings", row=1, disabled=False
    )
    async def change_pings(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Pings")

    @discord.ui.button(
        label="Change Users", style=discord.ButtonStyle.grey, custom_id="change_users", row=2, disabled=False
    )
    async def change_users(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.change_value(interaction, "Users")


from ui.views.manage_questions_select_view import ManageQuestionsSelect
from ui.views.manage_tickets_view import ManageTicketsView
