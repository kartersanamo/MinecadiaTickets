"""Shared helpers for ticket-logs V2 UI (avoids circular imports)."""

from __future__ import annotations

import discord

from ui.views.ticket_log_u_i_state_view import TicketLogUIState


class TicketLogsV2Support:
    @staticmethod
    async def tl_edit(interaction: discord.Interaction, state: TicketLogUIState) -> None:
        await refresh_ticket_logs_v2(interaction, state)


from ui.views.ticket_logs_v2_layout_view import refresh_ticket_logs_v2
