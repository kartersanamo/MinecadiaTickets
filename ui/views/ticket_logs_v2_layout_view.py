"""Ticket logs slash command — Components V2 browser for closed tickets."""

from __future__ import annotations

from typing import Any, Dict, List

import discord
from discord.enums import SeparatorSpacing

from core.config import ConfigManager
from services.ticket_log_service import TicketLogService
from ui.views.t_l_back_button_view import TLBackButton
from ui.views.t_l_jump_button_modal import TLJumpButton
from ui.views.t_l_mode_select_view import TLModeSelect
from ui.views.t_l_page_button_view import TLPageButton
from ui.views.t_l_pick_select_view import TLPickSelect
from ui.views.t_l_sort_select_view import TLSortSelect
from ui.views.t_l_type_select_view import TLTypeSelect
from ui.views.ticket_log_u_i_state_view import TicketLogUIState


class TicketLogsV2Layout(discord.ui.LayoutView):
    """Components V2 layout for /ticket-logs (list + detail + filters)."""

    def __init__(self, interaction: discord.Interaction, state: TicketLogUIState) -> None:
        super().__init__(timeout=600)
        self.state = state
        cfg = ConfigManager.all()
        self._logo_files, self._thumb = TicketLogService.logo_files_and_thumb(interaction, cfg)
        self._cfg = cfg
        rows = TicketLogService.fetch_rows(state.target.id, state.mode, state.sort_key, state.type_filter)
        self._rows = rows
        accent = TicketLogService.accent_int(cfg)
        inner: list = []

        if state.detail_channel_id is not None:
            self._build_detail(inner, interaction, accent)
        else:
            self._build_list(inner, interaction, accent, rows)

        self.add_item(discord.ui.Container(*inner, accent_color=accent))

    def _header_section(self, inner: list, title_md: str, interaction: discord.Interaction) -> None:
        if self._thumb:
            inner.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(title_md),
                    accessory=discord.ui.Thumbnail(
                        self._thumb,
                        description=(self._cfg.get("FOOTER") or "Logo")[:256],
                    ),
                )
            )
        else:
            inner.append(discord.ui.TextDisplay(title_md))

    def _build_detail(self, inner: list, interaction: discord.Interaction, accent: int) -> None:
        row = TicketLogService.row_by_channel(
            self._rows, self.state.detail_channel_id
        ) or TicketLogService.fetch_row_by_channel(
            int(self.state.detail_channel_id) if self.state.detail_channel_id is not None else 0
        )
        if not row:
            self._header_section(
                inner,
                "# Ticket details\n*That ticket could not be loaded. It may still be open or was removed.*",
                interaction,
            )
        else:
            title = f"# Ticket `#{TicketLogService.truncate(str(row.get('number') or ''), 24)}`\n*Full Record Below*"
            self._header_section(inner, title, interaction)
            inner.append(discord.ui.Separator(visible=True, spacing=SeparatorSpacing.large))
            for chunk in TicketLogService.format_detail_text(interaction, row):
                inner.append(discord.ui.TextDisplay(chunk))

        inner.append(discord.ui.Separator(visible=True, spacing=SeparatorSpacing.small))
        ar = discord.ui.ActionRow()
        ar.add_item(TLBackButton(self.state))
        show_t, _ = TicketLogService.staff_privacy(interaction, row) if row else (False, False)
        transcript = (row.get("transcript") or "").strip() if row else ""
        if row and show_t and transcript.startswith(("http://", "https://")):
            ar.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label="Transcript", url=transcript))
        inner.append(ar)

    def _build_list(
        self, inner: list, interaction: discord.Interaction, accent: int, rows: List[Dict[str, Any]]
    ) -> None:
        total = len(rows)
        max_page = max(0, (total - 1) // TicketLogService.PAGE_SIZE) if total else 0
        self.state.page = min(self.state.page, max_page)

        title = (
            f"# Ticket Logs\n"
            f"Browsing **{self.state.target.display_name}** (`{self.state.target.id}`)\n"
            f"Use the menus to switch perspective, sort, and filter. Pick a row to see **details**."
        )
        self._header_section(inner, title, interaction)

        inner.append(discord.ui.ActionRow(TLModeSelect(self.state)))
        inner.append(discord.ui.ActionRow(TLSortSelect(self.state)))

        all_types = TicketLogService.distinct_types(
            TicketLogService.fetch_rows(self.state.target.id, self.state.mode, self.state.sort_key, None)
        )
        if len(all_types) > 1:
            inner.append(discord.ui.ActionRow(TLTypeSelect(self.state, all_types[:24])))

        slice_rows = rows[
            self.state.page * TicketLogService.PAGE_SIZE : self.state.page * TicketLogService.PAGE_SIZE
            + TicketLogService.PAGE_SIZE
        ]
        inner.append(discord.ui.ActionRow(TLPickSelect(self.state, slice_rows, total)))

        page_count = max_page + 1 if total else 1
        inner.append(discord.ui.Separator(visible=True, spacing=SeparatorSpacing.small))
        for chunk in TicketLogService.build_page_quick_link_chunks(
            interaction, self.state, slice_rows, total, page_count, self._cfg
        ):
            inner.append(discord.ui.TextDisplay(chunk))

        nav = discord.ui.ActionRow(
            TLPageButton("⏮", "first", self.state, disabled=self.state.page <= 0),
            TLPageButton("◀", "prev", self.state, disabled=self.state.page <= 0),
            TLPageButton("▶", "next", self.state, disabled=self.state.page >= max_page or total == 0),
            TLPageButton("⏭", "last", self.state, disabled=self.state.page >= max_page or total == 0),
            TLJumpButton(self.state),
        )
        inner.append(nav)

        inner.append(discord.ui.Separator(visible=True, spacing=SeparatorSpacing.small))
        inner.append(discord.ui.TextDisplay(f"{self._cfg.get('FOOTER', '')}"))

    @property
    def content_length_safe(self) -> int:
        try:
            return self.content_length()
        except (AttributeError, TypeError, RuntimeError):
            return 0
