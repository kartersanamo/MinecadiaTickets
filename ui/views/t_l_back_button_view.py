from __future__ import annotations

import discord

from services.ticket_log_service import TicketLogService
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_support import TicketLogsV2Support


class TLBackButton(discord.ui.Button):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(style=discord.ButtonStyle.secondary, label="← Back to list", custom_id="tl_v2_back")

    async def callback(self, interaction: discord.Interaction) -> None:
        self._state.detail_channel_id = None
        await TicketLogsV2Support.tl_edit(interaction, self._state)
