from __future__ import annotations

import discord

from services.ticket_log_service import TicketLogService
from ui.modals.jump_ticket_modal import JumpTicketModal
from ui.views.ticket_log_u_i_state_view import TicketLogUIState


class TLJumpButton(discord.ui.Button):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(style=discord.ButtonStyle.primary, label="Jump #", custom_id="tl_v2_jump")

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(JumpTicketModal(self._state))
