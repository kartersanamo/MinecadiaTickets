from __future__ import annotations

import discord

from services.ticket_log_service import TicketLogService
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_support import TicketLogsV2Support


class TLTypeSelect(discord.ui.Select):
    def __init__(self, state: TicketLogUIState, types: list[str]) -> None:
        self._state = state
        options = [
            discord.SelectOption(
                label="All types",
                value="__all__",
                default=state.type_filter is None,
            )
        ]
        for ticket_type in types:
            options.append(
                discord.SelectOption(
                    label=TicketLogService.truncate(ticket_type, 100),
                    value=ticket_type,
                    default=state.type_filter == ticket_type,
                )
            )
        super().__init__(
            custom_id="tl_v2_type",
            placeholder="Filter by ticket type",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        chosen = self.values[0]
        self._state.type_filter = None if chosen == "__all__" else chosen
        self._state.page = 0
        self._state.detail_channel_id = None
        await TicketLogsV2Support.tl_edit(interaction, self._state)
