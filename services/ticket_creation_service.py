import json
import time

import discord

from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.loggers import log_tasks
from services.active_ticket_cache import active_ticket_cache
from services.embed_service import EmbedService
from ui.views.info_button import InfoButton

LOGO = "assets/Logo.png"


class TicketCreationService:
    def __init__(self):
        self.tickets = ConfigManager.tickets()

    @TaskDecorator.task("Check Cooldown Bypass", False)
    async def has_ticket_cooldown_bypass(self, interaction: discord.Interaction) -> bool:
        role_ids = ConfigManager.get("ROLE_IDS", {})
        bypass_ids = {
            int(role_ids.get("STAFF_TEAM_ROLE_ID", 0)),
            int(role_ids.get("ADMINISTRATOR_PERMS_ROLE_ID", 0)),
        }
        bypass_ids.discard(0)
        if not bypass_ids:
            return False
        user = interaction.user
        if not isinstance(user, discord.Member):
            return False
        member_role_ids = {int(r.id) for r in user.roles}
        return bool(member_role_ids & bypass_ids)

    @TaskDecorator.task("Get Ticket Count", False)
    async def get_ticket_count(self) -> int:
        row = DatabasePool.execute("SELECT COUNT(*) FROM tickets WHERE is_active = 1")
        return int(row[0]["COUNT(*)"])

    @TaskDecorator.task("Check Verified", False)
    async def check_verified(self, interaction: discord.Interaction) -> str | None:
        guild = interaction.guild
        if guild is None:
            return "`❌` You must be in a server to do this!"
        role = guild.get_role(ConfigManager.get("ROLE_IDS")["VERIFIED_ROLE_ID"])
        if role is None:
            return "`❌` The verified role was not found!"
        user = interaction.user
        if not isinstance(user, discord.Member):
            return "`❌` You must be a member of the server to do this!"
        if role not in user.roles:
            channel_id = ConfigManager.get("CHANNEL_IDS")["VERIFY_CHANNEL_ID"]
            if channel_id is None:
                return "`❌` The verify channel was not found!"
            channel = guild.get_channel(channel_id)
            if channel is None:
                return "`❌` The verify channel was not found!"
            log_tasks.warning(
                "%s (%s) is not verified and tried to open a ticket", interaction.user, interaction.user.id
            )
            return f"`❌` You are not verified! Go to the {channel.mention} channel and verify yourself first."
        return None

    @TaskDecorator.task("Check 5 Tickets", False)
    async def check_5_tickets(self, interaction: discord.Interaction) -> str | None:
        row = DatabasePool.execute(
            "SELECT COUNT(*) AS open_ticket_count FROM tickets WHERE owner_id = %s AND is_active = 1",
            (interaction.user.id,),
        )
        open_ticket_count = row[0]["open_ticket_count"]
        if open_ticket_count >= 5:
            log_tasks.warning(
                "%s (%s) has 5 tickets open and tried to open a ticket",
                interaction.user,
                interaction.user.id,
            )
            return "`❌` Failed! You already have **5** tickets open!"
        return None

    @TaskDecorator.task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction) -> str | None:
        row = DatabasePool.execute(
            "SELECT reason FROM blacklists WHERE user_id = %s",
            (interaction.user.id,),
        )
        if row:
            blacklist_reason = row[0]["reason"]
            log_tasks.warning(
                "%s (%s) is blacklisted from tickets and tried to open a ticket",
                interaction.user,
                interaction.user.id,
            )
            return (
                f"`❌` You are currently **blacklisted** from creating tickets "
                f"for the following reason\n```{blacklist_reason}```"
            )
        return None

    @TaskDecorator.task("Check Disabled", False)
    async def check_disabled(self, interaction: discord.Interaction) -> str | None:
        with open("assets/tickets.json", encoding="utf-8") as file:
            info = json.load(file)

        if info["TOGGLE_STATUS"] == "Disabled":
            log_tasks.warning(
                "%s (%s) tried to open a ticket when tickets are disabled",
                interaction.user,
                interaction.user.id,
            )
            return "`❌` Tickets are currently unavailable, please check again shortly."

        data = interaction.data
        if data is None:
            return "`❌` The data was not found!"
        category_name = data.get("custom_id")
        if category_name is None:
            return "`❌` The category name was not found!"
        values = data.get("values")
        if values is None or not isinstance(values, list):
            return "`❌` The values were not found!"
        ticket_type = values[0]
        if ticket_type is None:
            return "`❌` The ticket type was not found!"
        category_data = info.get(category_name, {})
        ticket_data = category_data.get(ticket_type, {})

        if ticket_data.get("Status") == "Disabled":
            log_tasks.warning(
                "%s (%s) tried to open a %s ticket when it is disabled",
                interaction.user,
                interaction.user.id,
                category_name,
            )
            return f"`❌` {category_name} tickets are currently unavailable, please check again shortly."
        return None

    @TaskDecorator.task("Check Recent Open", False)
    async def check_recent_open(self, interaction: discord.Interaction) -> str | None:
        if await self.has_ticket_cooldown_bypass(interaction):
            return None
        row = DatabasePool.execute(
            """
            SELECT opened_at FROM tickets
            WHERE owner_id = %s
            ORDER BY opened_at DESC
            LIMIT 1
            """,
            (interaction.user.id,),
        )

        if row:
            last_opened = float(row[0]["opened_at"])
            if time.time() - last_opened < 300:
                log_tasks.warning(
                    "%s (%s) opened a ticket too recent %sm %ss ago.",
                    interaction.user,
                    interaction.user.id,
                    int((time.time() - last_opened) // 60),
                    int((time.time() - last_opened) % 60),
                )
                return "`❌` You're opening tickets too fast! Please try again later."
        return None

    @TaskDecorator.task("Check Recent Closed", False)
    async def check_recent_closed(self, interaction: discord.Interaction) -> str | None:
        if await self.has_ticket_cooldown_bypass(interaction):
            return None
        row = DatabasePool.execute(
            """
            SELECT closed_at FROM tickets
            WHERE owner_id = %s AND is_active = 0
            ORDER BY closed_at DESC
            LIMIT 1
            """,
            (interaction.user.id,),
        )

        if row and row[0]["closed_at"]:
            last_closed = int(row[0]["closed_at"])
            if time.time() - last_closed < 120:
                log_tasks.warning(
                    "%s (%s) had a recently closed ticket %sm %ss ago.",
                    interaction.user,
                    interaction.user.id,
                    int((time.time() - last_closed) // 60),
                    int((time.time() - last_closed) % 60),
                )
                return "`❌` Your last ticket was just closed! Please try again later."
        return None

    @TaskDecorator.task("Check", False)
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

    @TaskDecorator.task("Get Ticket Number", False)
    async def get_number(self) -> int:
        row = DatabasePool.execute("SELECT COUNT(*) FROM tickets")
        return int(row[0]["COUNT(*)"]) + 1

    @TaskDecorator.task("Create Ticket", False)
    async def create_ticket(self, interaction: discord.Interaction) -> discord.TextChannel | None:
        data = interaction.data
        if data is None:
            return None
        custom_id = data.get("custom_id")
        if custom_id is None:
            return None
        values = data.get("values")
        if values is None or not isinstance(values, list) or not values:
            return None
        ticket_type_name = values[0]
        if not isinstance(ticket_type_name, str):
            return None
        category_tickets = self.tickets.get(custom_id)
        if not category_tickets:
            return None
        ticket_info = category_tickets.get(ticket_type_name)
        if ticket_info is None:
            return None
        ticket_type = f"{custom_id} ({ticket_type_name})"
        guild = interaction.guild
        if guild is None:
            return None
        category = guild.get_channel(ticket_info["Category"])
        if not isinstance(category, discord.CategoryChannel):
            return None
        staff = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        if staff is None:
            return None
        user = interaction.user
        if not isinstance(user, discord.Member):
            return None
        overwrites: dict[
            discord.Role | discord.Member | discord.Object,
            discord.PermissionOverwrite,
        ] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            staff: discord.PermissionOverwrite(view_channel=False),
        }
        for role_id in ticket_info["Roles"]:
            role_obj = guild.get_role(role_id)
            if role_obj is not None:
                overwrites[role_obj] = discord.PermissionOverwrite(view_channel=True)
        number = await self.get_number()
        channel = await guild.create_text_channel(
            name=f"{user.name}-ticket-{number}",
            category=category,
            overwrites=overwrites,
        )
        staff_team = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        if staff_team is None:
            return None
        panel_channel = interaction.channel
        if isinstance(panel_channel, discord.TextChannel):
            await panel_channel.set_permissions(staff_team, view_channel=False)
        embed = discord.Embed(
            description=f"✅ You have successfully opened a ticket! {channel.mention}",
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
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
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
            description=description,
        )
        logo_url = EmbedService.get_logo_url(LOGO)
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        await channel.send(
            embed=embed,
            view=InfoButton(ticket_type, ticket_info),
            file=discord.File("assets/Logo.png"),
        )
        privated = ""
        if any(substring in ticket_type for substring in ["Store Support", "Discord Issues", "Connection Issues"]):
            privated = "Admin"
        elif "Management Contact" in ticket_type:
            privated = "Management"
        DatabasePool.execute(
            "INSERT INTO tickets (channel_id, owner_id, type, opened_at, number, is_active, "
            "closed_by_id, closed_at, reason, name, transcript, privated) "
            "VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, NULL, %s)",
            (
                channel.id,
                interaction.user.id,
                category.name,
                int(time.time()),
                number,
                1,
                privated or None,
            ),
        )
        active_ticket_cache.register(channel.id, interaction.user.id)

        return channel

    @TaskDecorator.task(action_name="New Ticket")
    async def new_ticket(self, interaction: discord.Interaction, view: discord.ui.View) -> None:
        embed = discord.Embed(
            description=f"📖 Attempting to create a new ticket for {interaction.user.mention}",
            color=discord.Color.from_str(ConfigManager.get(key="EMBED_COLOR")),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        start = time.perf_counter()

        if not interaction.message:
            await interaction.response.send_message(content="`❌` Failed to edit the original interaction message")
        else:
            await interaction.message.edit(view=view)

        result = await self.check(interaction=interaction)
        if result:
            embed: discord.Embed = discord.Embed(
                description=result,
                color=discord.Color.from_str(ConfigManager.get(key="EMBED_COLOR")),
            )
            await interaction.edit_original_response(embed=embed)
            return

        channel = await self.create_ticket(interaction=interaction)
        if channel is None:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    description="`❌` Failed to create a ticket",
                    color=discord.Color.from_str(ConfigManager.get(key="EMBED_COLOR")),
                )
            )
            return
        ticket_count: int = await self.get_ticket_count()
        log_tasks.info(
            "Created #%s (%s) %s in %ss by %s (%s) %s",
            channel,
            channel.id,
            channel.category.name if channel.category is not None else "None",
            str(round((time.perf_counter() - start), 2)),
            interaction.user,
            interaction.user.id,
            ticket_count,
        )
