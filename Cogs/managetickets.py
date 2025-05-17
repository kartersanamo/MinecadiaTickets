#from Cogs.sendtickets import send_tickets_command
from Assets.functions import get_data, log_commands
from discord.ext import commands
from discord import app_commands
import discord
import json

################################################################
#                                                              #
#                                                              #
#   This file makes me want to puke. I will fix this later...  #
#                                                              #
#                                                              #
#                                            ... probably not  #
################################################################


data = get_data()

async def get_info():
    try:
        with open("MinecadiaTickets/Assets/tickets.json", "r") as file:
            info = json.load(file)
            del info['TOGGLE_STATUS']
            return info
    except Exception as e:
        log_commands.error(f"Failed to get info {e}")

async def update_msg(interaction: discord.Interaction):
    pass
    #try:
        #channel = interaction.guild.get_channel(data['CHANNEL_IDS']['TICKET_CHANNEL_ID'])
        #def is_bot(m):
        #    return m.author.bot
        #await channel.purge(limit = 4, check = is_bot)
        #command = interaction.client.tree.get_command("send-tickets")
        #cog = interaction.client.get_cog("Sendtickets")
        #await command.callback(self = cog, interaction = interaction, option = "Tickets", channel = channel)
        #await send_tickets_command(interaction, "Tickets", channel)
        #log_commands.info("Sent the new tickets message")
    #except Exception as e:
    #    log_commands.error(f"Failed to update the tickets message {e}")


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


class ManageCategoriesView(discord.ui.View):
    def __init__(self, ticket_info) -> None:
        super().__init__(timeout = None)
        self.ticket_info = ticket_info
        self.add_item(ManageCategoriesSelect(self.ticket_info))
        self.data = get_data()
    
    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await get_info()
            main_menu_embed = discord.Embed(title = "Main Menu",
                                color = discord.Color.from_str(self.data['EMBED_COLOR']),
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
            with open('MinecadiaTickets/Assets/tickets.json', 'r+') as file:
                data = json.load(file)
                data['TOGGLE_STATUS'] = 'Disabled' if data['TOGGLE_STATUS'] == 'Enabled' else 'Enabled'
                file.seek(0)
                json.dump(data, file, indent=3)
                file.truncate()
            log_commands.info(f"{interaction.user} ({interaction.user.id}) has toggled all tickets to {data['TOGGLE_STATUS']}")
            await interaction.followup.send(content = f"`✅` Successfully toggled all tickets to `{data['TOGGLE_STATUS']}`", ephemeral = True)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to toggle all tickets {e}")


class ManageCategoriesSelect(discord.ui.Select):
    def __init__(self, ticket_info) -> None:
        self.ticket_info = ticket_info
        labels = [category_name for category_name in list(self.ticket_info.keys())]
        options = [discord.SelectOption(label = label) for label in labels]
        super().__init__(placeholder = "Select a ticket category to manage...", options = options)
        self.data = get_data()

    async def callback(self, interaction: discord.Interaction):
        try:
            category = self.values[0]
            await interaction.response.defer()
            view = ManageTicketsView(self.ticket_info, category)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to select a ticket category {e}")


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
            with open("MinecadiaTickets/Assets/tickets.json", "r+") as file:
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


class ManageTicketsSelect(discord.ui.Select):
    def __init__(self, ticket_info, ticket_category) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        labels = [category_name for category_name in list(self.ticket_info.get(self.ticket_category).keys())]
        options = [discord.SelectOption(label = label) for label in labels]
        super().__init__(placeholder = "Select a ticket type to manage...", options = options)
        self.data = get_data()

    async def callback(self, interaction: discord.Interaction):
        try:
            ticket = self.values[0]
            await interaction.response.defer()
            view = ManageTypeView(self.ticket_info, self.ticket_category, ticket)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to select a ticket type in {self.ticket_category} {e}")

class ManageTypeView(discord.ui.View):
    def __init__(self, ticket_info, ticket_category, ticket) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        self.ticket = ticket
        super().__init__(timeout = None)
        self.data = get_data()
        self.add_item(ManageQuestionsSelect(self.ticket_info, self.ticket_category, self.ticket))
        self.mapping = {
            "Name": {
                "Description": "*This is the name of the ticket type, and will be displayed as the name on the drop down item.*",
                "Image": "https://i.imgur.com/EEcY2HU.png"
            },
            "Emoji": {
                "Description": "*This emoji will appear next to the ticket type's name after clicking on the ticket category.*",
                "Image": "https://i.imgur.com/vrgPt9q.png"
            },
            "Description": {
                "Description": "*This value will be displayed on the line next to the emoji to describe the ticket type.*",
                "Image": "https://i.imgur.com/xAsHZjW.png"
            },
            "Message": {
                "Description": "*This is the message that will be displayed in the ticket once the user opens the ticket. By default, the embed will show their name, the ticket type, and all of their questions/answers. This 'message' (such as revive rules) will be displayed after their last answer. After that will be a general message about staff support.*",
                "Image": "https://i.imgur.com/eD4qX3S.png"
            },
            "Roles": {
                "Description": "*These are the roles that can view the ticket channel when it is opened. By default, anyone with the* `*` *role can view the channel,* `@everyone` *cannot view it, and* `@Staff Team` *cannot view it. Any role in this list will be an addition to what was listed and will be able to view it and send messages. These roles in this list should ALWAYS match the roles that can view and send messages in the channel of the categories permissions. Otherwise, when moving to this category, permissions will adopt the permissions of the category, not the ones in this list.*\n \n`SEND THE ROLE IDs OF EACH ROLE SEPERATED BY A SPACE. ONE WRONG SPACE/CHARACTER AND IT WON'T WORK.`",
                "Image": "https://i.imgur.com/rTZ1k8H.png"
            },
            "Pings": {
                "Description": "*The pings represent a list of what roles will be pinged when the ticket is opened.*\n \n`SEND THE ROLE IDs OF EACH ROLE SEPERATED BY A SPACE. ONE WRONG SPACE/CHARACTER AND IT WON'T WORK.`",
                "Image": None
            },
            "Category": {
                "Description": "*This is the category that the ticket will be placed under when it is opened. Permissions for all tickets opened under this category are based on the permissions of the category. So please, make sure that the permissions are set up for that category first. For more information on how this works, read the 'Roles' blurb.*\n \n`SEND ONE SINGLE CATEGORY ID. ONE WRONG SPACE/CHARACTER AND IT WON'T WORK.`",
                "Image": None
            }
        }

    async def update_embed(self, interaction: discord.Interaction):
        try:
            self.ticket_info = await get_info()
            cat_info = self.ticket_info.get(self.ticket_category, {})
            ticket_info = cat_info.get(self.ticket, {})
            category = interaction.guild.get_channel(ticket_info.get('Category', "None"))
            category_string = f"{category.mention} ({category.id})" if category else "# None (0000000000000000)"
            pings = [interaction.guild.get_role(ping) for ping in ticket_info.get('Pings', [])]
            roles = [interaction.guild.get_role(role) for role in ticket_info.get('Roles', [])]
            pings = [ping.mention for ping in pings] if pings else ["None"]
            roles = [role.mention for role in roles] if roles else ["None"]
            if len(ticket_info.get('Message')) > 1000:
                message = f"```{ticket_info.get('Message')[:1000]}\n...```" if ticket_info.get('Message', None) else "None"
            else:
                message = f"```{ticket_info.get('Message')}```" if ticket_info.get('Message', None) else "None"
            manage_type_embed = discord.Embed(title = f"Manage Ticket Type",
                                            color = discord.Color.from_str(self.data['EMBED_COLOR']),
                                            description = self.ticket_category + " » " + self.ticket)
            manage_type_embed.add_field(name = "Status", value = ticket_info.get('Status', "None"))
            manage_type_embed.add_field(name = "Emoji", value = ticket_info.get('Emoji', "None"))
            manage_type_embed.add_field(name = "Description", value = ticket_info.get('Description', 'None'))
            manage_type_embed.add_field(name = "Category", value = category_string)
            manage_type_embed.add_field(name = "Pings", value = "".join(pings))
            manage_type_embed.add_field(name = "Roles", value = "".join(roles))
            manage_type_embed.add_field(name = "Message", value = message)
            questions_embed = discord.Embed(title = f"Manage Ticket Questions",
                                            color = discord.Color.from_str(self.data['EMBED_COLOR']),
                                            description = self.ticket_category + " » " + self.ticket)
            for question in ticket_info.get('Questions', [{}]):
                questions_embed.add_field(name = question.get('Label', 'None'), value = f"`»` {question.get('Placeholder', 'None')}\n `»` {question.get('Length', 'None')}")
            await interaction.edit_original_response(embeds = [manage_type_embed, questions_embed])
        except Exception as e:
            log_commands.error(f"Failed to update the embed {e}")
    
    async def change_value(self, interaction: discord.Interaction, value):
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
                if value == "Roles" or value == "Pings":
                    for role in m.content.split(" "):
                        try:
                            if not interaction.guild.get_role(int(role)):
                                return False
                        except:
                            return False
                if value == "Category":
                    try:
                        if not interaction.guild.get_channel(int(m.content)):
                            return False
                    except:
                        return False
                if m.channel == interaction.channel and m.author == interaction.user:
                    return True
                return False
            new_value = await interaction.client.wait_for('message', check = check)
            new_value.content = "" if new_value.content == "None" else new_value.content
            with open("MinecadiaTickets/Assets/tickets.json", "r+") as file:
                info = json.load(file)
                if value in ['Message', 'Description', 'Emoji']:
                    info[self.ticket_category][self.ticket][value] = new_value.content
                elif value == "Name":
                    info[self.ticket_category][new_value.content] = info[self.ticket_category].pop(self.ticket)
                    self.ticket = new_value.content
                elif value in ['Roles', 'Pings']:
                    info[self.ticket_category][self.ticket][value] = [int(role) for role in new_value.content.split(' ')]
                elif value == "Category":
                    info[self.ticket_category][self.ticket][value] = int(new_value.content)
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate() 
            await new_value.delete()
            view = ManageTypeView(self.ticket_info, self.ticket_category, self.ticket)
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
            view = ManageTicketsView(self.ticket_info, self.ticket_category)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to go back {e}")

    @discord.ui.button(label = "Toggle Status", style = discord.ButtonStyle.grey, custom_id = "toggle_status", row = 0, disabled = False)
    async def toggle_status(self, interaction: discord.Interaction, Button: discord.ui.Button):
        try:
            await interaction.response.defer()
            with open("MinecadiaTickets/Assets/tickets.json", "r+") as file:
                info = json.load(file)
                new_status = 'Enabled' if info[self.ticket_category][self.ticket]['Status'] == 'Disabled' else 'Disabled'
                info[self.ticket_category][self.ticket]['Status'] = new_status
                file.seek(0)
                json.dump(info, file, indent=3)
                file.truncate()
            view = ManageTypeView(self.ticket_info, self.ticket_category, self.ticket)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
            await update_msg(interaction)
            await interaction.followup.send(content = "Successfully toggled this ticket type.", ephemeral = True)
            log_commands.info(f"{interaction.user} ({interaction.user.id}) has toggled {self.ticket_category} {self.ticket} ticket type to {new_status}")
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to toggle ticket type of {self.ticket_category} {self.ticket} {e}")

    @discord.ui.button(label = "Change Name", style = discord.ButtonStyle.grey, custom_id = "change_name", row = 0, disabled = False)
    async def change_name(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Name")

    @discord.ui.button(label = "Change Emoji", style = discord.ButtonStyle.grey, custom_id = "change_emoji", row = 0, disabled = False)
    async def change_emoji(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Emoji")
    
    @discord.ui.button(label = "Change Description", style = discord.ButtonStyle.grey, custom_id = "change_description", row = 0, disabled = False)
    async def change_description(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Description")
    
    @discord.ui.button(label = "Change Category", style = discord.ButtonStyle.grey, custom_id = "change_category", row = 1, disabled = False)
    async def change_category(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Category")
    
    @discord.ui.button(label = "Change Message", style = discord.ButtonStyle.grey, custom_id = "change_message", row = 1, disabled = False)
    async def change_message(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Message")

    @discord.ui.button(label = "Change Roles", style = discord.ButtonStyle.grey, custom_id = "change_roles", row = 1, disabled = False)
    async def change_roles(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Roles")

    @discord.ui.button(label = "Change Pings", style = discord.ButtonStyle.grey, custom_id = "change_pings", row = 1, disabled = False)
    async def change_pings(self, interaction: discord.Interaction, Button: discord.ui.Button):
        await self.change_value(interaction, "Pings")


class ManageQuestionsSelect(discord.ui.Select):
    def __init__(self, ticket_info, ticket_category, ticket) -> None:
        self.ticket_info = ticket_info
        self.ticket_category = ticket_category
        self.ticket = ticket
        labels = [question.get('Label', 'None') for question in list(self.ticket_info.get(self.ticket_category, {self.ticket_category: {self.ticket: {"Questions": [{'Label': 'None'}]}}}).get(self.ticket, {self.ticket: {"Questions": [{'Label': 'None'}]}}).get('Questions', [{'Label': 'None'}]))]
        options = [discord.SelectOption(label = label) for label in labels]
        super().__init__(placeholder = "Select a question to manage...", options = options)
        self.data = get_data()
    
    async def callback(self, interaction: discord.Interaction):
        try:
            question = self.values[0]
            await interaction.response.defer()
            view = ManageQuestionView(self.ticket_info, self.ticket_category, self.ticket, question)
            await view.update_embed(interaction)
            await interaction.message.edit(view = view)
        except Exception as e:
            log_commands.error(f"{interaction.user} ({interaction.user.id}) has failed to select a question to manage in {self.ticket_category} {self.ticket} {e}")


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
            with open("MinecadiaTickets/Assets/tickets.json", "r+") as file:
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
            with open("MinecadiaTickets/Assets/tickets.json", "r+") as file:
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


async def setup(client: commands.Bot) -> None:
    await client.add_cog(ManageTickets(client))