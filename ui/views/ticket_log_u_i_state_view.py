"""UI state for /ticket-logs Components V2 browser."""

from __future__ import annotations

from typing import Literal, Optional

import discord


class TicketLogUIState:
    __slots__ = ("target", "mode", "sort_key", "type_filter", "page", "detail_channel_id")

    def __init__(self, target: discord.Member) -> None:
        self.target = target
        self.mode: Literal["owner", "closer"] = "owner"
        self.sort_key: Literal["opened_at", "closed_at"] = "opened_at"
        self.type_filter: Optional[str] = None
        self.page: int = 0
        self.detail_channel_id: Optional[int] = None

    def show_list(self) -> None:
        self.detail_channel_id = None
        self.page = 0

    def show_detail(self, channel_id: int) -> None:
        self.detail_channel_id = channel_id
        self.page = 0
