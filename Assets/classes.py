from Assets.functions import task, log_tasks, get_data, execute, get_ticket_data, get_embed_logo_url
from enum import Enum
import discord
import random
import json
import time

LOGO = "Assets/Logo.png"

class TicketCategory(Enum):
    GENERAL = "General"
    BUG = "Bug"
    PLAYER = "Player"
    APPEAL = "Appeal"
    REVIVE = "Revive"
    ROLLBACK = "Rollback"
    ISSUE = "Issue"
    APPLICATIONS = "Applications"
    MEDIA = "Media"


class Paginator(discord.ui.View):
    def __init__(self) -> None:
      super().__init__(timeout = None)
      self.data : list # Expecting this to be assiged after instantiation
      self.title : str # Expecting this to be assiged after instantiation
      self.sorted: str = None # Optional
      self.sep = 5 # Expecting this to be assiged after instantiation
      self.current_page = 1 # LEAVE AS 1
      self.category : discord.Category = None # Optional
      self.count : bool = False # Optional

    async def send(self, interaction: discord.Interaction):
      try:
        await interaction.response.send_message(view=self, content="")
      except:
        await interaction.edit_original_response(view=self, content="")
      await self.update_message(interaction)

    def create_embed(self):
      embed = discord.Embed(title=self.title, description="",  color=discord.Color.gold())
      footer_text = self.get_footer_text()
      if self.data[0] == "No data found.":
        embed.description = "No data found."
      else:
        if self.count:
          for index, item in enumerate(self.get_current_page_data()):
            embed.description += f"**{(self.sep*self.current_page)-(self.sep-(index+1))}.** {item}\n"
        else:
          for item in self.get_current_page_data():
            embed.description += f"{item}\n"
      if footer_text:
        logo_url = get_embed_logo_url(LOGO)
        embed.set_footer(icon_url = logo_url, text = footer_text)
      return embed

    async def update_message(self, interaction: discord.Interaction):
      self.update_buttons()
      await interaction.edit_original_response(embed=self.create_embed(), view=self)

    def update_buttons(self):
      if self.data[0] == "No data found.":
        return
      total_pages = (int(len(self.data) / self.sep))
      total_pages += 1 if int(len(self.data)) % self.sep != 0 else 0
      is_first_page = self.current_page == 1
      is_last_page = self.current_page == total_pages
      self.first_page_button.disabled = is_first_page
      self.prev_button.disabled = is_first_page
      self.first_page_button.style = discord.ButtonStyle.gray if is_first_page else discord.ButtonStyle.red
      self.prev_button.style = discord.ButtonStyle.gray if is_first_page else discord.ButtonStyle.red
      self.next_button.disabled = is_last_page
      self.last_page_button.disabled = is_last_page
      self.last_page_button.style = discord.ButtonStyle.gray if is_last_page else discord.ButtonStyle.red
      self.next_button.style = discord.ButtonStyle.gray if is_last_page else discord.ButtonStyle.red

    def get_current_page_data(self):
      until_item = self.current_page * self.sep
      from_item = until_item - self.sep if self.current_page != 1 else 0
      return self.data[from_item:until_item]

    def get_footer_text(self):
      total_pages = (int(len(self.data) / self.sep))
      total_pages += 1 if int(len(self.data)) % self.sep != 0 else 0
      footer_text: str = f"Page {self.current_page}/{total_pages} ({len(self.data)} total) | Minecadia Tickets Bot"
      footer_text += self.sorted if self.sorted else ""
      return footer_text

    async def handle_page_button(self, interaction: discord.Interaction, step: int):
      await interaction.response.defer()
      self.current_page += step
      await self.update_message(interaction)

    @discord.ui.button(label="|<", style=discord.ButtonStyle.gray, disabled=True, custom_id="lskip")
    async def first_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
      await self.handle_page_button(interaction, 1 - self.current_page)

    @discord.ui.button(label="<", style=discord.ButtonStyle.gray, disabled=True, custom_id="left")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
      await self.handle_page_button(interaction, -1)

    @discord.ui.button(label=">", style=discord.ButtonStyle.gray, disabled=True, custom_id="right")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
      await self.handle_page_button(interaction, 1)

    @discord.ui.button(label=">|", style=discord.ButtonStyle.gray, disabled=True, custom_id="rskip")
    async def last_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
      total_pages = (int(len(self.data) / self.sep))
      total_pages += 1 if int(len(self.data)) % self.sep != 0 else 0
      await self.handle_page_button(interaction, total_pages - self.current_page)


class Questions(discord.ui.Modal):
    def __init__(self, ticket_type: str, ticket_info) -> None:
        self.ticket_type = ticket_type
        self.ticket_info = ticket_info
        self.ticket_type = self.ticket_type[:45] if len(self.ticket_type) > 45 else self.ticket_type
        super().__init__(title=self.ticket_type,
                         timeout=None,
                         custom_id=str(random.randint(0, 50000000000)))
        self.tickets = get_ticket_data()
        self.data = get_data()
        # Headings in the same order as TextInput children — avoids reading ``TextInput.label``
        # (deprecated in newer discord.py in favor of ``discord.ui.Label``).
        self._modal_field_headings: list = []
        self.add_items()

    def add_items(self):
        try:
            ign_label = "What is your in game name?"
            self.add_item(
                discord.ui.TextInput(
                    label = ign_label,
                    placeholder = "My IGN is...",
                    style = discord.TextStyle.short,
                    custom_id = str(random.randint(0, 50000)),
                )
            )
            self._modal_field_headings.append(ign_label)
            for question in self.ticket_info['Questions']:
                style = discord.TextStyle.short if question['Length'] == "Short" else discord.TextStyle.long
                q_label = question['Label']
                input = discord.ui.TextInput(
                    label = q_label,
                    placeholder = question['Placeholder'],
                    style = style,
                    custom_id = str(random.randint(0, 50000)),
                )
                self.add_item(input)
                self._modal_field_headings.append(q_label)

        except Exception as e:
            log_tasks.error(f"Failed to add items to the Questions modal {e}")

    @task("Get Previous Ticket", False)
    async def get_previous_ticket(self, owner_id: int) -> discord.Embed:
        rows = execute(f"SELECT name, number, reason, transcript, closed_at, closed_by, privated FROM tickets WHERE ownerID = '{owner_id}' AND active = 'False' ORDER BY CAST(closed_at AS INTEGER) DESC LIMIT 1")
        if not rows: return None
        else:
            embed: discord.Embed
            if rows[0]['privated']:
                embed = discord.Embed(
                    title = f"Recently Closed {rows[0]['name']}#{rows[0]['number']}",
                    description = f"Closed by <@{rows[0]['closed_by']}> on <t:{rows[0]['closed_at']}:f> (<t:{rows[0]['closed_at']}:R>)\nReason: Privated Ticket",
                    color = discord.Color.from_str(self.data["EMBED_COLOR"])
                )
            else:
               embed = discord.Embed(
                    title = f"Recently Closed {rows[0]['name']}#{rows[0]['number']}",
                    description = f"Closed by <@{rows[0]['closed_by']}> on <t:{rows[0]['closed_at']}:f> (<t:{rows[0]['closed_at']}:R>)\nReason: {rows[0]['reason']}\n[Ticket Transcript]({rows[0]['transcript']})",
                    color = discord.Color.from_str(self.data["EMBED_COLOR"])
                )
            logo_url = get_embed_logo_url(self.data["LOGO"])
            embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
            return embed

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            roles = [interaction.guild.get_role(ping).mention for ping in self.ticket_info['Pings']]
            tags = await interaction.channel.send(" ".join(roles))
            embed = interaction.message.embeds[0]
            split = embed.description.split("\n\n")
            new_description = f"{split[0]}\n \n{split[1]}\n \n"
            for heading, item in zip(self._modal_field_headings, self.children):
                if not isinstance(item, discord.ui.TextInput):
                    continue
                if heading == "What is your in game name?" or heading == "What is the offending player's IGN?":
                    new_description += f"**{heading}**\n`{item.value}`\n \n"
                else:
                    new_description += f"**{heading}**\n{item.value}\n \n"
            new_description += "\n\n".join(split[2:])
            embed = discord.Embed(description=new_description, color=discord.Color.from_str(self.data["EMBED_COLOR"]))
            
            # Set footer BEFORE editing the message
            logo_url = get_embed_logo_url(self.data["LOGO"])
            embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
            
            # Get previous ticket and edit message with both embeds (or just one if no previous)
            previous_ticket: discord.Embed = await self.get_previous_ticket(owner_id = interaction.user.id)
            if previous_ticket:
                await interaction.message.edit(embeds = [embed, previous_ticket], view = None)
            else:
                await interaction.message.edit(embed = embed, view = None)
            
            perms = interaction.channel.overwrites_for(interaction.user)
            perms.send_messages = perms.view_channel = True
            await interaction.channel.set_permissions(interaction.user, overwrite=perms)
            await tags.delete()
            log_tasks.info(f"{interaction.user} ({interaction.user.id}) updated the embed with question answers in #{interaction.channel} ({interaction.channel.id})")
            
        except Exception as e:
            log_tasks.error(f"{interaction.user} ({interaction.user.id}) failed to add question answers into embed {e}")


class InfoButton(discord.ui.View):
    def __init__(self, ticket_type: str, ticket_info) -> None:
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        self.ticket_info = ticket_info
        self.data = get_data()

    @discord.ui.button(label="Enter Information",
                       style=discord.ButtonStyle.grey,
                       custom_id="enter_information")
    async def enter_information_button(self, interaction: discord.Interaction, Button: discord.ui.Button):
        try:
            await interaction.response.send_modal(Questions(self.ticket_type, self.ticket_info))
            log_tasks.info(f"Sent the Questions modal to {interaction.user} ({interaction.user.id})")
        except Exception as e:
            log_tasks.error(f"Failed to send the Questions modal to {interaction.user} ({interaction.user.id}) {e}")


class TicketSystem:
    def __init__(self):
        self.data: dict = get_data()
        self.tickets = get_ticket_data()

    @task("Get Ticket Count", False)
    async def get_ticket_count(self) -> int:
        row = execute("SELECT COUNT(*) FROM tickets WHERE active = 'True'")
        return int(row[0]['COUNT(*)'])

    @task("Check Verified", False)
    async def check_verified(self, interaction: discord.Interaction) -> str:
        role = interaction.guild.get_role(self.data['ROLE_IDS']['VERIFIED_ROLE_ID'])
        if role not in interaction.user.roles:
            channel = interaction.guild.get_channel(self.data['CHANNEL_IDS']['VERIFY_CHANNEL_ID'])
            log_tasks.warning(f"{interaction.user} ({interaction.user.id}) is not verified and tried to open a ticket")
            return f"`❌` You are not verified! Go to the {channel.mention} channel and verify yourself first."
        return None

    @task("Check 5 Tickets", False)
    async def check_5_tickets(self, interaction: discord.Interaction) -> str:
        row = execute(f"SELECT COUNT(*) AS open_ticket_count FROM tickets WHERE ownerID = '{interaction.user.id}' AND active = 'True'")
        open_ticket_count = row[0]["open_ticket_count"]
        if open_ticket_count >= 5:
            log_tasks.warning(f"{interaction.user} ({interaction.user.id}) has 5 tickets open and tried to open a ticket")
            return "`❌` Failed! You already have **5** tickets open!"
        return None

    @task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction) -> str:
        row = execute(f"SELECT reason FROM blacklists WHERE userID = '{interaction.user.id}'")
        if row:
            blacklist_reason = row[0]["reason"]
            log_tasks.warning(f"{interaction.user} ({interaction.user.id}) is blacklisted from tickets and tried to open a ticket")
            return f"`❌` You are currently **blacklisted** from creating tickets for the following reason\n```{blacklist_reason}```"
        return None

    @task("Check Disabled", False)
    async def check_disabled(self, interaction: discord.Interaction) -> str:
        with open("Assets/tickets.json", "r") as file:
            info = json.load(file)
            
        if info['TOGGLE_STATUS'] == 'Disabled':
            log_tasks.warning(f"{interaction.user} ({interaction.user.id}) tried to open a ticket when tickets are disabled")
            return "`❌` Tickets are currently unavailable, please check again shortly."
        
        category_name = interaction.data['custom_id']
        ticket_type = interaction.data['values'][0]
        category_data = info.get(category_name, {})
        ticket_data = category_data.get(ticket_type, {})

        if ticket_data.get('Status') == 'Disabled':
            log_tasks.warning(f"{interaction.user} ({interaction.user.id}) tried to open a {category_name} ticket when it is disabled")
            return f"`❌` {category_name} tickets are currently unavailable, please check again shortly."
        
        return None

    @task("Check Recent Open", False)
    async def check_recent_open(self, interaction: discord.Interaction) -> str:
        row = execute(f"""
            SELECT opened_at FROM tickets 
            WHERE ownerID = '{interaction.user.id}' 
            ORDER BY opened_at DESC 
            LIMIT 1
        """)
        
        if row:
            last_opened = float(row[0]["opened_at"])
            if time.time() - last_opened < 300: 
                log_tasks.warning(f"{interaction.user} ({interaction.user.id}) opened a ticket too recent.")
                return "`❌` You're opening tickets too fast! Please try again later."
        return None
    
    @task("Check Recent Closed", False)
    async def check_recent_closed(self, interaction: discord.Interaction) -> str:
        row = execute(f"""
            SELECT closed_at FROM tickets 
            WHERE ownerID = '{interaction.user.id}' AND active = 'False'
            ORDER BY closed_at DESC 
            LIMIT 1
        """)
        
        if row and row[0]["closed_at"]:
            last_closed = int(row[0]["closed_at"])
            if time.time() - last_closed < 120: 
                log_tasks.warning(f"{interaction.user} ({interaction.user.id}) had a recently closed ticket.")
                return "`❌` Your last ticket was just closed! Please try again later."
        return None


    @task("Check", False)
    async def check(self, interaction: discord.Interaction):
        check_functions: list = [
            self.check_verified,
            self.check_5_tickets,
            self.check_blacklisted,
            self.check_disabled,
            self.check_recent_open,
            self.check_recent_closed
        ]

        for check_function in check_functions:
            error: str = await check_function(interaction)
            if error:
                return error

        return None
    
    @task("Get Ticket Number", False)
    async def get_number(self) -> int:
        row = execute("SELECT COUNT(*) FROM tickets")
        return int(row[0]['COUNT(*)']) + 1

    @task("Create Ticket", False)
    async def create_ticket(self, interaction: discord.Interaction) -> discord.TextChannel:
        channel: discord.TextChannel
        custom_id = interaction.data['custom_id']
        ticket_type = interaction.data['values'][0]
        ticket_info = self.tickets[custom_id][ticket_type]
        ticket_type = f"{custom_id} ({ticket_type})"
        category = interaction.guild.get_channel(ticket_info['Category'])
        staff = interaction.guild.get_role(self.data['ROLE_IDS']['STAFF_TEAM_ROLE_ID'])
        permissions = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            staff: discord.PermissionOverwrite(view_channel=False)
        }
        for role in ticket_info['Roles']:
            role_obj = interaction.guild.get_role(role)
            permissions.update({
                role_obj: discord.PermissionOverwrite(view_channel=True)
            })
        number = await self.get_number()
        channel = await interaction.guild.create_text_channel(
            name = f"{interaction.user.name}-ticket-{number}", 
            category = category,
            overwrites = permissions
        )
        staff_team = interaction.guild.get_role(self.data['ROLE_IDS']['STAFF_TEAM_ROLE_ID'])
        await interaction.channel.set_permissions(staff_team, view_channel = False)
        embed = discord.Embed(
            description = f"✅ You have successfully opened a ticket! {channel.mention}",
            color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        await interaction.edit_original_response(embed = embed)
        description = (f"Hey {interaction.user.mention}!\n"
                        "\n"
                        "You have created a new ticket!\n"
                        f"**Type:** {ticket_type}\n"
                        "\n")
        description += ticket_info['Message'] + "\n \n**One of our staff members will be with you shortly.**"
        embed = discord.Embed(
            color = discord.Color.from_str(self.data["EMBED_COLOR"]),
            description = description
        )
        logo_url = get_embed_logo_url(LOGO)
        embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
        await channel.send(embed = embed, view = InfoButton(ticket_type, ticket_info), file = discord.File("Assets/Logo.png"))
        privated = "" 
        if any(substring in ticket_type for substring in ["Store Support", "Discord Issues", "Connection Issues"]):
            privated = "Admin"
        elif "Management Contact" in ticket_type:
            privated = "Management"
        execute(f"INSERT INTO tickets (channelID, ownerID, type, opened_at, number, active, closed_by, closed_at, reason, name, transcript, privated) VALUES ('{channel.id}', '{interaction.user.id}', '{category.name}', '{int(time.time())}', '{number}', 'True', ' ', ' ', ' ', ' ', ' ', '{privated}')")
        
        return channel
            
    @task("New Ticket", False)
    async def new_ticket(self, interaction: discord.Interaction, view: discord.ui.View) -> None:
        embed = discord.Embed(
            description = f"📖 Attempting to create a new ticket for {interaction.user.mention}",
            color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        await interaction.response.send_message(embed = embed, ephemeral = True)
        start = time.perf_counter()
        await interaction.message.edit(view = view)
        result = await self.check(interaction)  
        if result:
            embed = discord.Embed(
                description = result,
                color = discord.Color.from_str(self.data["EMBED_COLOR"])
            )
            return await interaction.edit_original_response(embed = embed)
        channel: discord.TextChannel = await self.create_ticket(interaction)
        ticket_count: int = await self.get_ticket_count()
        log_tasks.info(f"Created #{channel} ({channel.id}) in {str(round((time.perf_counter() - start), 2))}s by {interaction.user} ({interaction.user.id}) {ticket_count}")