from __future__ import annotations

import discord

from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_support import TicketLogsV2Support


class TLSortSelect(discord.ui.Select):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(
            custom_id="tl_v2_sort",
            placeholder="Sort by…",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="Opened (newest first)",
                    value="opened_at",
                    default=state.sort_key == "opened_at",
                ),
                discord.SelectOption(
                    label="Closed (newest first)",
                    value="closed_at",
                    default=state.sort_key == "closed_at",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self._state.sort_key = self.values[0]  # type: ignore[assignment]
        self._state.page = 0
        self._state.detail_channel_id = None
        await TicketLogsV2Support.tl_edit(interaction, self._state)
