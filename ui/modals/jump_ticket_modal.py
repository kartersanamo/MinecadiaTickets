"""Jump-to-ticket modal for ticket logs V2."""

from __future__ import annotations

from typing import Any, Dict

import discord

from services.ticket_log_service import TicketLogService
from ui.views.ticket_log_u_i_state_view import TicketLogUIState


class JumpTicketModal(discord.ui.Modal, title="Jump to ticket #"):
    number = discord.ui.TextInput(
        label="Ticket number",
        placeholder="Digits from the ticket channel / log",
        min_length=1,
        max_length=32,
        required=True,
    )

    def __init__(self, state: TicketLogUIState) -> None:
        super().__init__(timeout=300)
        self._state = state

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = (self.number.value or "").strip()
        row = TicketLogService.fetch_row_by_number(self._state.target.id, self._state.mode, raw)
        if not row:
            await interaction.response.send_message(
                f"No matching closed ticket **#{TicketLogService.truncate(raw, 32)}** for this perspective.",
                ephemeral=True,
            )
            return
        self._state.detail_channel_id = int(row["channel_id"])
        self._state.page = 0
        from ui.views.ticket_logs_v2_layout_view import TicketLogsV2Layout

        view = TicketLogsV2Layout(interaction, self._state)
        kwargs: Dict[str, Any] = {"content": None, "view": view}
        if view._logo_files:
            kwargs["attachments"] = view._logo_files
        await interaction.response.edit_message(**kwargs)
