from __future__ import annotations

from typing import Any, Dict, List

import discord

from services.ticket_log_service import TicketLogService
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_support import TicketLogsV2Support


class TLPageButton(discord.ui.Button):
    def __init__(self, emoji: str, action: str, state: TicketLogUIState, *, disabled: bool) -> None:
        self._state = state
        self._action = action
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=f"tl_pg_{action}", disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        rows = TicketLogService.fetch_rows(
            self._state.target.id, self._state.mode, self._state.sort_key, self._state.type_filter
        )
        total = len(rows)
        max_page = max(0, (total - 1) // TicketLogService.PAGE_SIZE) if total else 0
        if self._action == "first":
            self._state.page = 0
        elif self._action == "prev":
            self._state.page = max(0, self._state.page - 1)
        elif self._action == "next":
            self._state.page = min(max_page, self._state.page + 1)
        else:
            self._state.page = max_page
        self._state.detail_channel_id = None
        await TicketLogsV2Support.tl_edit(interaction, self._state)
