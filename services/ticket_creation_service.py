import json
import os
import time

import aiohttp
import discord

from core.config import get_settings, get_ticket_data
from core.database import execute
from core.decorators import task
from core.loggers import log_tasks

LOGO = "assets/Logo.png"


class TicketCreationService:
    def __init__(self):
        self.data: dict = get_settings()
        self.tickets = get_ticket_data()

    @task("Check Cooldown Bypass", False)
    async def has_ticket_cooldown_bypass(self, interaction: discord.Interaction) -> bool:
        role_ids = self.data.get("ROLE_IDS", {})
        bypass_ids = {
            int(role_ids.get("STAFF_TEAM_ROLE_ID", 0)),
            int(role_ids.get("ADMINISTRATOR_PERMS_ROLE_ID", 0)),
        }
        bypass_ids.discard(0)
        if not bypass_ids:
            return False
        member_role_ids = {int(r.id) for r in interaction.user.roles}
        return bool(member_role_ids & bypass_ids)

    async def notify_dashboard_new_ticket(
        self,
        channel: discord.TextChannel,
        number: int,
        ticket_type: str,
        owner_id: int,
    ) -> None:
        base_url = os.getenv("DASHBOARD_URL", "https://bots.kartersanamo.com").rstrip("/")
        endpoint = (
            os.getenv("DASHBOARD_TICKET_NOTIFY_URL", "").strip()
            or f"{base_url}/api/tickets/live-events"
        )
        secret = os.getenv("TICKETS_BOT_API_SECRET") or os.getenv("CONTROL_API_SECRET")
        if not endpoint or not secret:
            return

        payload = {
            "kind": "ticket_created",
            "channelId": str(channel.id),
            "ticketNumber": str(number),
            "ticketType": str(ticket_type),
            "ownerId": str(owner_id),
            "channelName": str(channel.name),
        }
        headers = {"X-Tickets-Key": secret, "Content-Type": "application/json"}
        timeout = aiohttp.ClientTimeout(total=2.5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, json=payload, headers=headers) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        log_tasks.warning(
                            f"Dashboard new-ticket notify failed ({resp.status}): {body[:200]}"
                        )
        except Exception as e:
            log_tasks.warning(f"Dashboard new-ticket notify error: {e}")

    @task("Get Ticket Count", False)
    async def get_ticket_count(self) -> int:
        row = execute("SELECT COUNT(*) FROM tickets WHERE active = 'True'")
        return int(row[0]["COUNT(*)"])

    @task("Check Verified", False)
    async def check_verified(self, interaction: discord.Interaction) -> str:
        role = interaction.guild.get_role(self.data["ROLE_IDS"]["VERIFIED_ROLE_ID"])
        if role not in interaction.user.roles:
            channel = interaction.guild.get_channel(
                self.data["CHANNEL_IDS"]["VERIFY_CHANNEL_ID"]
            )
            log_tasks.warning(
                f"{interaction.user} ({interaction.user.id}) is not verified and tried to open a ticket"
            )
            return f"`❌` You are not verified! Go to the {channel.mention} channel and verify yourself first."
        return None

    @task("Check 5 Tickets", False)
    async def check_5_tickets(self, interaction: discord.Interaction) -> str:
        row = execute(
            f"SELECT COUNT(*) AS open_ticket_count FROM tickets WHERE ownerID = '{interaction.user.id}' AND active = 'True'"
        )
        open_ticket_count = row[0]["open_ticket_count"]
        if open_ticket_count >= 5:
            log_tasks.warning(
                f"{interaction.user} ({interaction.user.id}) has 5 tickets open and tried to open a ticket"
            )
            return "`❌` Failed! You already have **5** tickets open!"
        return None

    @task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction) -> str:
        row = execute(f"SELECT reason FROM blacklists WHERE userID = '{interaction.user.id}'")
        if row:
            blacklist_reason = row[0]["reason"]
            log_tasks.warning(
                f"{interaction.user} ({interaction.user.id}) is blacklisted from tickets and tried to open a ticket"
            )
            return f"`❌` You are currently **blacklisted** from creating tickets for the following reason\n```{blacklist_reason}```"
        return None

    @task("Check Disabled", False)
    async def check_disabled(self, interaction: discord.Interaction) -> str:
        with open("assets/tickets.json", "r") as file:
            info = json.load(file)

        if info["TOGGLE_STATUS"] == "Disabled":
            log_tasks.warning(
                f"{interaction.user} ({interaction.user.id}) tried to open a ticket when tickets are disabled"
            )
            return "`❌` Tickets are currently unavailable, please check again shortly."

        category_name = interaction.data["custom_id"]
        ticket_type = interaction.data["values"][0]
        category_data = info.get(category_name, {})
        ticket_data = category_data.get(ticket_type, {})

        if ticket_data.get("Status") == "Disabled":
            log_tasks.warning(
                f"{interaction.user} ({interaction.user.id}) tried to open a {category_name} ticket when it is disabled"
            )
            return f"`❌` {category_name} tickets are currently unavailable, please check again shortly."

        return None

    @task("Check Recent Open", False)
    async def check_recent_open(self, interaction: discord.Interaction) -> str:
        if await self.has_ticket_cooldown_bypass(interaction):
            return None
        row = execute(f"""
            SELECT opened_at FROM tickets
            WHERE ownerID = '{interaction.user.id}'
            ORDER BY opened_at DESC
            LIMIT 1
        """)

        if row:
            last_opened = float(row[0]["opened_at"])
            if time.time() - last_opened < 300:
                log_tasks.warning(
                    f"{interaction.user} ({interaction.user.id}) opened a ticket too recent."
                )
                return "`❌` You're opening tickets too fast! Please try again later."
        return None

    @task("Check Recent Closed", False)
    async def check_recent_closed(self, interaction: discord.Interaction) -> str:
        if await self.has_ticket_cooldown_bypass(interaction):
            return None
        row = execute(f"""
            SELECT closed_at FROM tickets
            WHERE ownerID = '{interaction.user.id}' AND active = 'False'
            ORDER BY closed_at DESC
            LIMIT 1
        """)

        if row and row[0]["closed_at"]:
            last_closed = int(row[0]["closed_at"])
            if time.time() - last_closed < 120:
                log_tasks.warning(
                    f"{interaction.user} ({interaction.user.id}) had a recently closed ticket."
                )
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
            self.check_recent_closed,
        ]

        for check_function in check_functions:
            error: str = await check_function(interaction)
            if error:
                return error

        return None

    @task("Get Ticket Number", False)
    async def get_number(self) -> int:
        row = execute("SELECT COUNT(*) FROM tickets")
        return int(row[0]["COUNT(*)"]) + 1

    @task("Create Ticket", False)
    async def create_ticket(self, interaction: discord.Interaction) -> discord.TextChannel:
        custom_id = interaction.data["custom_id"]
        ticket_type = interaction.data["values"][0]
        ticket_info = self.tickets[custom_id][ticket_type]
        ticket_type = f"{custom_id} ({ticket_type})"
        category = interaction.guild.get_channel(ticket_info["Category"])
        staff = interaction.guild.get_role(self.data["ROLE_IDS"]["STAFF_TEAM_ROLE_ID"])
        permissions = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            staff: discord.PermissionOverwrite(view_channel=False),
        }
        for role in ticket_info["Roles"]:
            role_obj = interaction.guild.get_role(role)
            permissions.update({role_obj: discord.PermissionOverwrite(view_channel=True)})
        number = await self.get_number()
        channel = await interaction.guild.create_text_channel(
            name=f"{interaction.user.name}-ticket-{number}",
            category=category,
            overwrites=permissions,
        )
        staff_team = interaction.guild.get_role(self.data["ROLE_IDS"]["STAFF_TEAM_ROLE_ID"])
        await interaction.channel.set_permissions(staff_team, view_channel=False)
        embed = discord.Embed(
            description=f"✅ You have successfully opened a ticket! {channel.mention}",
            color=discord.Color.from_str(self.data["EMBED_COLOR"]),
        )
        await interaction.edit_original_response(embed=embed)
        description = (
            f"Hey {interaction.user.mention}!\n"
            "\n"
            "You have created a new ticket!\n"
            f"**Type:** {ticket_type}\n"
            "\n"
        )
        description += ticket_info["Message"] + "\n \n**One of our staff members will be with you shortly.**"
        embed = discord.Embed(
            color=discord.Color.from_str(self.data["EMBED_COLOR"]),
            description=description,
        )
        logo_url = interaction.client.app.embeds.get_logo_url(LOGO)
        embed.set_footer(text=self.data["FOOTER"], icon_url=logo_url)
        from ui.views.info_button import InfoButton

        await channel.send(
            embed=embed,
            view=InfoButton(ticket_type, ticket_info),
            file=discord.File("assets/Logo.png"),
        )
        privated = ""
        if any(
            substring in ticket_type
            for substring in ["Store Support", "Discord Issues", "Connection Issues"]
        ):
            privated = "Admin"
        elif "Management Contact" in ticket_type:
            privated = "Management"
        execute(
            f"INSERT INTO tickets (channelID, ownerID, type, opened_at, number, active, closed_by, closed_at, reason, name, transcript, privated) VALUES ('{channel.id}', '{interaction.user.id}', '{category.name}', '{int(time.time())}', '{number}', 'True', ' ', ' ', ' ', ' ', ' ', '{privated}')"
        )

        return channel

    @task("New Ticket", False)
    async def new_ticket(self, interaction: discord.Interaction, view: discord.ui.View) -> None:
        embed = discord.Embed(
            description=f"📖 Attempting to create a new ticket for {interaction.user.mention}",
            color=discord.Color.from_str(self.data["EMBED_COLOR"]),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        start = time.perf_counter()
        await interaction.message.edit(view=view)
        result = await self.check(interaction)
        if result:
            embed = discord.Embed(
                description=result,
                color=discord.Color.from_str(self.data["EMBED_COLOR"]),
            )
            return await interaction.edit_original_response(embed=embed)
        channel: discord.TextChannel = await self.create_ticket(interaction)
        ticket_count: int = await self.get_ticket_count()
        log_tasks.info(
            f"Created #{channel} ({channel.id}) in {str(round((time.perf_counter() - start), 2))}s by {interaction.user} ({interaction.user.id}) {ticket_count}"
        )
