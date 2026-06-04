import asyncio
import random

import discord

from core.config import get_settings, get_ticket_data
from core.database import execute
from core.decorators import task
from core.loggers import log_tasks
from utils.embeds import get_embed_logo_url


class Questions(discord.ui.Modal):
    def __init__(self, ticket_type: str, ticket_info) -> None:
        self.ticket_type = ticket_type
        self.ticket_info = ticket_info
        self.ticket_type = self.ticket_type[:45] if len(self.ticket_type) > 45 else self.ticket_type
        super().__init__(
            title=self.ticket_type,
            timeout=None,
            custom_id=str(random.randint(0, 50000000000)),
        )
        self.tickets = get_ticket_data()
        self.data = get_settings()
        self._modal_field_headings: list = []
        self.add_items()

    def add_items(self):
        try:
            ign_label = "What is your in game name?"
            self.add_item(
                discord.ui.TextInput(
                    label=ign_label,
                    placeholder="My IGN is...",
                    style=discord.TextStyle.short,
                    custom_id=str(random.randint(0, 50000)),
                )
            )
            self._modal_field_headings.append(ign_label)
            for question in self.ticket_info["Questions"]:
                style = (
                    discord.TextStyle.short
                    if question["Length"] == "Short"
                    else discord.TextStyle.long
                )
                q_label = question["Label"]
                input_field = discord.ui.TextInput(
                    label=q_label,
                    placeholder=question["Placeholder"],
                    style=style,
                    custom_id=str(random.randint(0, 50000)),
                )
                self.add_item(input_field)
                self._modal_field_headings.append(q_label)

        except Exception as e:
            log_tasks.error(f"Failed to add items to the Questions modal {e}")

    @task("Get Previous Ticket", False)
    async def get_previous_ticket(self, owner_id: int) -> discord.Embed:
        rows = execute(
            f"SELECT name, number, reason, transcript, closed_at, closed_by, privated FROM tickets WHERE ownerID = '{owner_id}' AND active = 'False' ORDER BY CAST(closed_at AS INTEGER) DESC LIMIT 1"
        )
        if not rows:
            return None
        if rows[0]["privated"]:
            embed = discord.Embed(
                title=f"Recently Closed {rows[0]['name']}#{rows[0]['number']}",
                description=(
                    f"Closed by <@{rows[0]['closed_by']}> on <t:{rows[0]['closed_at']}:f> "
                    f"(<t:{rows[0]['closed_at']}:R>)\nReason: Privated Ticket"
                ),
                color=discord.Color.from_str(self.data["EMBED_COLOR"]),
            )
        else:
            embed = discord.Embed(
                title=f"Recently Closed {rows[0]['name']}#{rows[0]['number']}",
                description=(
                    f"Closed by <@{rows[0]['closed_by']}> on <t:{rows[0]['closed_at']}:f> "
                    f"(<t:{rows[0]['closed_at']}:R>)\nReason: {rows[0]['reason']}\n"
                    f"[Ticket Transcript]({rows[0]['transcript']})"
                ),
                color=discord.Color.from_str(self.data["EMBED_COLOR"]),
            )
        logo_url = get_embed_logo_url(self.data["LOGO"])
        embed.set_footer(text=self.data["FOOTER"], icon_url=logo_url)
        return embed

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            roles = [interaction.guild.get_role(ping).mention for ping in self.ticket_info["Pings"]]
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
            embed = discord.Embed(
                description=new_description, color=discord.Color.from_str(self.data["EMBED_COLOR"])
            )

            logo_url = get_embed_logo_url(self.data["LOGO"])
            embed.set_footer(text=self.data["FOOTER"], icon_url=logo_url)

            previous_ticket: discord.Embed = await self.get_previous_ticket(
                owner_id=interaction.user.id
            )
            if previous_ticket:
                await interaction.message.edit(embeds=[embed, previous_ticket], view=None)
            else:
                await interaction.message.edit(embed=embed, view=None)

            perms = interaction.channel.overwrites_for(interaction.user)
            perms.send_messages = perms.view_channel = True
            await interaction.channel.set_permissions(interaction.user, overwrite=perms)
            await tags.delete()
            log_tasks.info(
                f"{interaction.user} ({interaction.user.id}) updated the embed with question answers in #{interaction.channel} ({interaction.channel.id})"
            )

            rows = execute(
                f"SELECT number FROM tickets WHERE channelID = '{interaction.channel.id}' LIMIT 1"
            )
            if rows:
                from domain.ticket_system import TicketSystem

                asyncio.create_task(
                    TicketSystem().notify_dashboard_new_ticket(
                        channel=interaction.channel,
                        number=int(rows[0]["number"]),
                        ticket_type=self.ticket_type,
                        owner_id=interaction.user.id,
                    )
                )

        except Exception as e:
            log_tasks.error(
                f"{interaction.user} ({interaction.user.id}) failed to add question answers into embed {e}"
            )
