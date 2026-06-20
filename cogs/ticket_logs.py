"""
ticket_logs.py

Cog for the ticket logs command (Components V2 browser).

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

from __future__ import annotations

from typing import Any, Dict

import discord
from discord import app_commands
from discord.ext import commands

from core.config import ConfigManager
from core.decorators import TaskDecorator
from services.ticket_log_service import TicketLogService
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_layout_view import TicketLogsV2Layout


class TicketLogs(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client = client

    @TaskDecorator.task(action_name="Ticket Logs Command", log=True)
    async def ticket_logs_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await interaction.response.defer()
        state = TicketLogUIState(user)
        view = TicketLogsV2Layout(interaction, state)
        kwargs: Dict[str, Any] = {"content": None, "view": view}
        if view._logo_files:
            kwargs["attachments"] = view._logo_files
        if view.content_length_safe > 4000:
            fb = discord.ui.LayoutView(timeout=600)
            fb.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(
                        "# Ticket Logs\n"
                        "This response would exceed Discord limits. "
                        "Try a **type filter** or the other **perspective** to narrow results."
                    ),
                    accent_color=TicketLogService.accent_int(ConfigManager.all()),
                )
            )
            await interaction.edit_original_response(content=None, view=fb)
            return
        await interaction.edit_original_response(**kwargs)

    @app_commands.guild_only()
    @app_commands.command(name="ticket-logs", description="Browse closed tickets for a member (Components V2)")
    @app_commands.describe(user="Member to look up")
    async def ticketlogs(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.ticket_logs_command(interaction, user)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketLogs(client))
