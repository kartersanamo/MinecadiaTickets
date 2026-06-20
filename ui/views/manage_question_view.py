import json
from typing import Any

import discord

from core.config import ConfigManager
from core.errors.exceptions import UI_CALLBACK_ERRORS
from core.loggers import log_commands
from ui.views.manage_tickets_support import ManageTicketsSupport


class ManageQuestionView(discord.ui.View):
    def __init__(self, ticket_info, ticket_category, ticket, question) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        self.ticket = ticket
        self.question = question
        self.mapping = {
            "Label": {
                "Description": "*This is the label of the question that appears above the text box. The max length on a modal title is 45 characters.*",
                "Image": "https://i.imgur.com/GrYinyp.png",
            },
            "Placeholder": {
                "Description": "*This message will be in the text box before the user types anything in. Usually, this is where directions go about what to enter into the text box. The max length of a modal's placeholder is 100 characters.*",
                "Image": "https://i.imgur.com/Ad07AYo.png",
            },
        }
        super().__init__(timeout=None)

    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await ConfigManager.reload_tickets()
            questions = self.ticket_info.get(self.ticket_category, {}).get(self.ticket, {}).get("Questions") or []
            question_info = next((question for question in questions if question.get("Label") == self.question), None)
            if question_info is None:
                return
            embed = discord.Embed(
                title="Manage Ticket Questions",
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
                description=self.ticket_category + " » " + self.ticket,
            )
            embed.add_field(name="Question", value=question_info.get("Label", "None"))
            embed.add_field(name="Placeholder", value=question_info.get("Placeholder", "None"))
            embed.add_field(name="Length", value=question_info.get("Length", "None"))
            await interaction.edit_original_response(embed=embed)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("Failed to update embed %s", e)

    async def change_value(self, interaction: discord.Interaction, value: str):
        try:
            guild = interaction.guild
            if guild is None:
                return await interaction.response.send_message(
                    content="You must be in a server to do this!", ephemeral=True
                )
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

            def check(m):
                if value == "Label":
                    if len(m.content) > 45:
                        return False
                else:
                    if len(m.content) > 100:
                        return False
                if m.channel == interaction.channel and m.author == interaction.user:
                    return True
                return False

            new_value = await interaction.client.wait_for("message", check=check)
            with open("assets/tickets.json", "r+", encoding="utf-8") as file:
                info = json.load(file)
                questions = info.get(self.ticket_category, {}).get(self.ticket, {}).get("Questions") or []
                index = next(
                    (i for i, question in enumerate(questions) if question.get("Label") == self.question),
                    None,
                )
                if index is None:
                    return
                popped = questions.pop(index)
                popped[value] = new_value.content
                questions.insert(index, popped)
                info[self.ticket_category][self.ticket]["Questions"] = questions
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            if value == "Label":
                self.question = new_value.content
            await new_value.delete()
            view = ManageQuestionView(self.ticket_info, self.ticket_category, self.ticket, self.question)
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
    async def go_back_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from ui.views.manage_type_view import ManageTypeView

            await interaction.response.defer()
            view = ManageTypeView(self.ticket_info, self.ticket_category, self.ticket)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
        except UI_CALLBACK_ERRORS as e:
            log_commands.error("%s (%s) has failed to go back %s", interaction.user, interaction.user.id, e)

    @discord.ui.button(
        label="Change Label", style=discord.ButtonStyle.grey, custom_id="change_question", row=0, disabled=False
    )
    async def change_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_value(interaction, "Label")

    @discord.ui.button(
        label="Change Placeholder",
        style=discord.ButtonStyle.grey,
        custom_id="change_placeholder",
        row=0,
        disabled=False,
    )
    async def change_placeholder(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_value(interaction, "Placeholder")

    @discord.ui.button(
        label="Change Length", style=discord.ButtonStyle.grey, custom_id="change_length", row=0, disabled=False
    )
    async def change_length(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = interaction.guild
            if guild is None:
                return await interaction.response.send_message(
                    content="You must be in a server to do this!", ephemeral=True
                )
            star_role = guild.get_role(ConfigManager.get("ROLE_IDS")["ADMINISTRATOR_PERMS_ROLE_ID"])
            if star_role is None:
                return await interaction.response.send_message(
                    content="Administrator permissions role not found!", ephemeral=True
                )
            if not isinstance(interaction.user, discord.Member) or not star_role in interaction.user.roles:
                return await interaction.response.send_message(content="You can't do this!", ephemeral=True)
            await interaction.response.defer()
            with open("assets/tickets.json", "r+", encoding="utf-8") as file:
                info = json.load(file)
                questions = info.get(self.ticket_category, {}).get(self.ticket, {}).get("Questions") or []
                index = next(
                    (i for i, question in enumerate(questions) if question.get("Label") == self.question),
                    None,
                )
                if index is None:
                    return
                popped = questions.pop(index)
                new_length = "Short" if popped["Length"] == "Long" else "Long"
                popped["Length"] = new_length
                questions.insert(index, popped)
                info[self.ticket_category][self.ticket]["Questions"] = questions
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            view = ManageQuestionView(self.ticket_info, self.ticket_category, self.ticket, self.question)
            await view.update_embed(interaction)
            if interaction.message is not None:
                await interaction.message.edit(view=view)
            await interaction.followup.send(content="Successfully changed the length.", ephemeral=True)
            await ManageTicketsSupport.update_msg(interaction)
            log_commands.info(
                "%s (%s) has changed the length of %s %s question %s to %s",
                interaction.user,
                interaction.user.id,
                self.ticket_category,
                self.ticket,
                self.question,
                new_length,
            )
        except UI_CALLBACK_ERRORS as e:
            log_commands.error(
                "%s (%s) has failed to change the length %s", interaction.user, interaction.user.id, e
            )
