"""
ticket_count.py

This file is the cog for the ticket count command. It is used to display
the number of tickets open in the server.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator


class TicketCount(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client

    @TaskDecorator.task("Get Active List", False)
    async def get_active_list(self) -> list[dict]:
        rows = DatabasePool.execute(
            "SELECT type, COUNT(*) as count FROM tickets WHERE is_active = 1 GROUP BY type ORDER BY count DESC"
        )
        return rows

    @TaskDecorator.task("Get Total List", False)
    async def get_total_list(self) -> list[dict]:
        rows = DatabasePool.execute("SELECT type, COUNT(*) as count FROM tickets GROUP BY type ORDER BY count DESC")
        return rows

    @TaskDecorator.task("Get Debug Embeds", False)
    async def get_debug_embeds(
        self, active_list: list[dict], active_count: int, total_list: list[dict], total_count: int
    ) -> list[discord.Embed]:
        active_embed = discord.Embed(
            title="Active Tickets By Category",
            description="\n".join(
                f"> **{row.get('count', 0)}** {row.get('type', 'Unknown')} ({round(row.get('count', 0) / active_count * 100, 2)}%)"
                for row in active_list
            ),
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
        )
        active_embed.set_footer(text=f"There are {active_count:,} tickets open!")
        history_embed = discord.Embed(
            title="Total Ticket History",
            description="\n".join(
                f"> **{row.get('count', 0)}** {row.get('type', 'Unknown')} ({round(row.get('count', 0) / total_count * 100, 2)}%)"
                for row in total_list
            ),
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
        )
        history_embed.set_footer(text=f"There have been {total_count:,} total tickets!")
        return [active_embed, history_embed]

    @app_commands.guild_only()
    @app_commands.command(name="ticket-count", description="Sends the number of currently opened tickets")
    async def ticketcount(self, interaction: discord.Interaction, debug: Optional[Literal["Yes"]] = None):
        await self.ticket_count_command(interaction, debug)

    @TaskDecorator.task("Ticket Count Command", True)
    async def ticket_count_command(
        self, interaction: discord.Interaction, debug: Optional[Literal["Yes"]] = None
    ) -> None:
        active_list: list[dict] = await self.get_active_list()
        active_count: int = sum(row.get("count", 0) for row in active_list)

        total_list: list[dict] = await self.get_total_list()
        total_count: int = sum(row.get("count", 0) for row in total_list)

        embed_list: list[discord.Embed] = []

        if not debug:
            embed = discord.Embed(
                title=f"There are **{active_count}** tickets open!",
                color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
            )
            embed.set_footer(text=f"There have been {total_count:,} total tickets!")
            embed_list.append(embed)
        else:
            debug_embeds: list[discord.Embed] = await self.get_debug_embeds(
                active_list, active_count, total_list, total_count
            )
            embed_list.extend(debug_embeds)

        await interaction.response.send_message(embeds=embed_list)


async def setup(client: TicketsBot) -> None:
    await client.add_cog(TicketCount(client))
