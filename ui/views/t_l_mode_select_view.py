from __future__ import annotations

import discord

from services.ticket_log_service import TicketLogService
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_support import TicketLogsV2Support


class TLModeSelect(discord.ui.Select):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(
            custom_id="tl_v2_mode",
            placeholder="Whose tickets?",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=TicketLogService.truncate(f"Opened by {state.target.display_name}", 100),
                    value="owner",
                    description="They were the ticket owner",
                    default=state.mode == "owner",
                ),
                discord.SelectOption(
                    label=TicketLogService.truncate(f"Closed by {state.target.display_name}", 100),
                    value="closer",
                    description="They clicked close / closed the ticket",
                    default=state.mode == "closer",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self._state.mode = self.values[0]  # type: ignore[assignment]
        self._state.page = 0
        self._state.type_filter = None
        self._state.detail_channel_id = None
        await TicketLogsV2Support.tl_edit(interaction, self._state)
