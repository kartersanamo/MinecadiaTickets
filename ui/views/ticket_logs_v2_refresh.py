"""Refresh handler for /ticket-logs Components V2 views."""

from __future__ import annotations

from typing import Any

import discord

from ui.views.ticket_log_u_i_state_view import TicketLogUIState


def build_ticket_logs_view(interaction: discord.Interaction, state: TicketLogUIState):
    from ui.views.ticket_logs_v2_layout_view import TicketLogsV2Layout

    return TicketLogsV2Layout(interaction, state)


async def refresh_ticket_logs_v2(interaction: discord.Interaction, state: TicketLogUIState) -> None:
    view = build_ticket_logs_view(interaction, state)
    kwargs: dict[str, Any] = {"content": None, "view": view}
    if view.logo_files:
        kwargs["attachments"] = view.logo_files
    await interaction.response.edit_message(**kwargs)
