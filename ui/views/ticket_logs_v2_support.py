"""Shared helpers for ticket-logs V2 UI (avoids circular imports)."""

from __future__ import annotations

from typing import Any

import discord

from ui.views.ticket_log_u_i_state_view import TicketLogUIState


class TicketLogsV2Support:
    @staticmethod
    async def tl_edit(interaction: discord.Interaction, state: TicketLogUIState) -> None:
        from ui.views.ticket_logs_v2_layout_view import TicketLogsV2Layout

        view = TicketLogsV2Layout(interaction, state)
        kwargs: dict[str, Any] = {"content": None, "view": view}
        if view._logo_files:
            kwargs["attachments"] = view._logo_files
        await interaction.response.edit_message(**kwargs)
