#from cogs.sendtickets import send_tickets_command
from discord.ext import commands
from discord import app_commands
import discord
import json
from core.config import get_data
from core.loggers import log_commands


class ManageQuestionView(discord.ui.View):
    def __init__(self, ticket_info, ticket_category, ticket, question) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        self.ticket = ticket
        self.question = question
        self.mapping = {
            "Label": {
                "Description": "*This is the label of the question that appears above the text box. The max length on a modal title is 45 characters.*",
                "Image": "https://i.imgur.com/GrYinyp.png"
            },
            "Placeholder": {
                "Description": "*This message will be in the text box before the user types anything in. Usually, this is where directions go about what to enter into the text box. The max length of a modal's placeholder is 100 characters.*",
                "Image": "https://i.imgur.com/Ad07AYo.png"
            }
        }
        super().__init__(timeout = None)
        self.data = get_data()
    
    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await get_info()
            questions = self.ticket_info.get(self.ticket_category).get(self.ticket).get('Questions')
            for question in questions:
                if question.get('Label') == self.question:
                    question_info = question
            embed = discord.Embed(title = "Manage Ticket Questions",
                                color = discord.Color.from_str(self.data['EMBED_COLOR']),
                                description = self.ticket_category + " » " + self.ticket)
            embed.add_field(name = "Question", value = question_info.get('Label'))
            embed.add_field(name = "Placeholder", value = question_info.get('Placeholder'))
            embed.add_field(name = "Length", value = question_info.get('Length'))
            await interaction.edit_original_response(embed = embed)
        except Exception as e:
            log_commands.error(f"Failed to update embed {e}")

    async def change_value(self, interaction: discord.Interaction, value: str):
        try:
            star_role = interaction.guild.get_role(self.data['ROLE_IDS']['ADMINISTRATOR_PERMS_ROLE_ID']) 
            if not star_role in interaction.user.roles:
                return await interaction.response.send_message(content = "You can't do this!", ephemeral = True)
            await interaction.response.defer()
            await self.update_embed(interaction)
            top_embed = interaction.message.embeds[0]
            description, image = list(self.mapping.get(value).values())
            embed = discord.Embed(title = f"Enter the new {value.lower()} below",
                                color = discord.Color.from_str(self.data['EMBED_COLOR']),
                                description = description)
            embed.set_image(url = image)
            await interaction.message.edit(embeds = [top_embed, embed], view = None)
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
            new_value = await interaction.client.wait_for('message', check = check)
            with open("assets/tickets.json", "r+") as file:
                info = json.load(file)
                questions = info.get(self.ticket_category).get(self.ticket).get('Questions')
                for index, question in enumerate(questions):
                    if question.get('Label') == self.question:
                        popped = questions.pop(index)
                        ind = index
                popped[value] = new_value.content
                questions.insert(ind, popped)
                info[self.ticket_category][self.ticket]['Questions'] = questions
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            if value == "Label":
                self.question = new_value.content
            await new_value.delete()
            view = ManageQuestionView(self.ticket_info, self.ticket_category, self.ticket, self.question)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
            await update_msg(interaction)
            log_commands.info(f"{interaction.user} ({interaction.user.id}) has changed {value} to {new_value} for {self.ticket_category} {self.ticket}")
        except Exception as e:
            log_commands.error(f"Failed to change the value of {value} {e}")

    @discord.ui.button(label = "|<", style = discord.ButtonStyle.red, custom_id = "go_back_type", row = 0, disabled = False)
    async def go_back_type(self, interaction: discord.Interaction, Button: discord.ui.Button):
        try:
            await interaction.response.defer()
            view = ManageTypeView(self.ticket_info, self.ticket_category, self.ticket)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to go back {e}")

    @discord.ui.button(label = "Change Label", style = discord.ButtonStyle.grey, custom_id = "change_question", row = 0, disabled = False)
    async def change_question(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Label")
    
    @discord.ui.button(label = "Change Placeholder", style = discord.ButtonStyle.grey, custom_id = "change_placeholder", row = 0, disabled = False)
    async def change_placeholder(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Placeholder")
    
    @discord.ui.button(label = "Change Length", style = discord.ButtonStyle.grey, custom_id = "change_length", row = 0, disabled = False)
    async def change_length(self, interaction: discord.Interaction, Button: discord.ui.Button):
        try:
            star_role = interaction.guild.get_role(self.data['ROLE_IDS']['ADMINISTRATOR_PERMS_ROLE_ID']) 
            if not star_role in interaction.user.roles:
                return await interaction.response.send_message(content = "You can't do this!", ephemeral = True)
            await interaction.response.defer()
            with open("assets/tickets.json", "r+") as file:
                info = json.load(file)
                questions = info.get(self.ticket_category).get(self.ticket).get('Questions')
                for index, question in enumerate(questions):
                    if question.get('Label') == self.question:
                        popped = questions.pop(index)
                        ind = index
                new_length = 'Short' if popped['Length'] == 'Long' else 'Long'
                popped['Length'] = new_length
                questions.insert(ind, popped)
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            view = ManageQuestionView(self.ticket_info, self.ticket_category, self.ticket, self.question)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
            await interaction.followup.send(content = "Successfully changed the length.", ephemeral = True)
            await update_msg(interaction)
            log_commands.info(f"{interaction.user} ({interaction.user.id}) has changed the length of {self.ticket_category} {self.ticket} question {self.question} to {new_length}")
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to change the length {e}")
