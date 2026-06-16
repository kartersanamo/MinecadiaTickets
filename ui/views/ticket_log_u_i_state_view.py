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
