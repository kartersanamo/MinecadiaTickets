from __future__ import annotations

from typing import Any, Dict, List

import discord

from services.ticket_log_service import TicketLogService
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_support import TicketLogsV2Support


class TLPickSelect(discord.ui.Select):
    def __init__(self, state: TicketLogUIState, slice_rows: List[Dict[str, Any]], total: int) -> None:
        self._state = state
        if not slice_rows:
            super().__init__(
                custom_id="tl_v2_pick",
                placeholder="No closed tickets in this view",
                min_values=1,
                max_values=1,
                options=[discord.SelectOption(label="—", value="__none__")],
                disabled=True,
            )
            return
        opts: List[discord.SelectOption] = []
        base = state.page * TicketLogService.PAGE_SIZE
        for index, row in enumerate(slice_rows):
            idx = base + index + 1
            cid = int(row["channel_id"])
            num = str(row.get("number") or "?")
            typ = (str(row.get("type") or "Unknown")).replace("\n", " ")
            name = (str(row.get("name") or "—")).replace("\n", " ")
            ts = TicketLogService.safe_int_ts(row.get(state.sort_key))
            label = TicketLogService.truncate(f"{idx}. #{num} · {typ} · {name}", 100)
            desc = TicketLogService.format_select_option_date(ts) if ts is not None else "Unknown date"
            opts.append(
                discord.SelectOption(
                    label=label,
                    value=str(cid),
                    description=TicketLogService.truncate(desc, 100),
                )
            )
        super().__init__(
            custom_id="tl_v2_pick",
            placeholder=f"Open a ticket… ({total} total)",
            min_values=1,
            max_values=1,
            options=opts[:25],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.disabled or self.values[0] == "__none__":
            return
        self._state.detail_channel_id = int(self.values[0])
        await TicketLogsV2Support.tl_edit(interaction, self._state)
