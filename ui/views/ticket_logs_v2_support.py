"""Shared helpers for ticket-logs V2 UI (avoids circular imports)."""

from __future__ import annotations

import discord

from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_refresh import refresh_ticket_logs_v2


class TicketLogsV2Support:
    @staticmethod
    async def tl_edit(interaction: discord.Interaction, state: TicketLogUIState) -> None:
        await refresh_ticket_logs_v2(interaction, state)

    @staticmethod
    async def tl_defer(interaction: discord.Interaction) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()
