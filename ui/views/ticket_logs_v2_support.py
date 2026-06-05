"""Shared helpers for ticket-logs V2 UI (avoids circular imports)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import discord

from ui.views.ticket_log_u_i_state_view import TicketLogUIState


def _row_by_channel(
    rows: List[Dict[str, Any]],
    channel_id: Optional[int],
) -> Optional[Dict[str, Any]]:
    if channel_id is None:
        return None
    cid = int(channel_id)
    for row in rows:
        try:
            if int(row.get("channel_id") or 0) == cid:
                return row
        except (TypeError, ValueError):
            continue
    return None


async def _tl_edit(interaction: discord.Interaction, state: TicketLogUIState) -> None:
    from ui.views.ticket_logs_v2_layout_view import TicketLogsV2Layout

    view = TicketLogsV2Layout(interaction, state)
    kwargs: dict[str, Any] = {"content": None, "view": view}
    if view._logo_files:
        kwargs["attachments"] = view._logo_files
    await interaction.response.edit_message(**kwargs)
