import asyncio
import random

import discord

from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.loggers import log_tasks
from services.embed_service import EmbedService


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
        self.tickets = ConfigManager.tickets()
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

    @TaskDecorator.task("Get Previous Ticket", False)
    async def get_previous_ticket(self, owner_id: int) -> discord.Embed | None:
        rows = DatabasePool.execute(
            "SELECT name, number, reason, transcript, closed_at, closed_by_id, privated FROM tickets "
            "WHERE owner_id = %s AND is_active = 0 ORDER BY closed_at DESC LIMIT 1",
            (owner_id,),
        )
        if not rows:
            return None
        if rows[0]["privated"]:
            embed = discord.Embed(
                title=f"Recently Closed {rows[0]['name']}#{rows[0]['number']}",
                description=(
                    f"Closed by <@{rows[0]['closed_by_id']}> on <t:{rows[0]['closed_at']}:f> "
                    f"(<t:{rows[0]['closed_at']}:R>)\nReason: Privated Ticket"
                ),
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
            )
        else:
            embed = discord.Embed(
                title=f"Recently Closed {rows[0]['name']}#{rows[0]['number']}",
                description=(
                    f"Closed by <@{rows[0]['closed_by_id']}> on <t:{rows[0]['closed_at']}:f> "
                    f"(<t:{rows[0]['closed_at']}:R>)\nReason: {rows[0]['reason']}\n"
                    f"[Ticket Transcript]({rows[0]['transcript']})"
                ),
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
            )
        logo_url = EmbedService.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        return embed

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()

            guild = interaction.guild
            channel = interaction.channel
            message = interaction.message
            user = interaction.user
            if (
                guild is None
                or not isinstance(channel, discord.TextChannel)
                or not isinstance(user, discord.Member)
                or message is None
                or message.embeds is None
            ):
                return

            roles = [
                role.mention
                for ping in self.ticket_info["Pings"]
                if (role := guild.get_role(ping)) is not None
            ]
            tags = await channel.send(" ".join(roles))
            embed = message.embeds[0]
            if embed.description is None:
                await tags.delete()
                return

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
                description=new_description, color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR"))
            )

            logo_url = EmbedService.get_logo_url(ConfigManager.get("LOGO"))
            embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)

            previous_ticket: discord.Embed | None = await self.get_previous_ticket(
                owner_id=interaction.user.id
            )
            if previous_ticket:
                await message.edit(embeds=[embed, previous_ticket], view=None)
            else:
                await message.edit(embed=embed, view=None)

            perms = channel.overwrites_for(user)
            perms.send_messages = perms.view_channel = True
            await channel.set_permissions(user, overwrite=perms)
            await tags.delete()
            log_tasks.info(
                f"{interaction.user} ({interaction.user.id}) updated the embed with question answers in #{channel} ({channel.id})"
            )

            rows = DatabasePool.execute(
                "SELECT number FROM tickets WHERE channel_id = %s LIMIT 1", (channel.id,)
            )
            if rows:
                from services.ticket_creation_service import TicketCreationService as TicketSystem

                asyncio.create_task(
                    TicketSystem().notify_dashboard_new_ticket(
                        channel=channel,
                        number=int(rows[0]["number"]),
                        ticket_type=self.ticket_type,
                        owner_id=interaction.user.id,
                    )
                )

        except Exception as e:
            log_tasks.error(
                f"{interaction.user} ({interaction.user.id}) failed to add question answers into embed {e}"
            )
