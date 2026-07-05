from __future__ import annotations

import time
from dataclasses import dataclass

import discord

from core.database import DatabasePool
from services.active_ticket_cache import active_ticket_cache

STALE_TICKET_REASON = "Channel deleted (stale ticket sync)"


@dataclass(frozen=True)
class StaleTicketSyncResult:
    active_tickets_checked: int
    stale_channel_ids: list[int]

    @property
    def cleared_count(self) -> int:
        return len(self.stale_channel_ids)


class StaleTicketService:
    @classmethod
    def clear_stale_tickets(cls, guild: discord.Guild) -> StaleTicketSyncResult:
        rows = DatabasePool.execute("SELECT channel_id FROM tickets WHERE is_active = 1")
        stale_channel_ids: list[int] = []

        for row in rows:
            channel_id = int(row["channel_id"])
            if guild.get_channel(channel_id) is None:
                stale_channel_ids.append(channel_id)

        if stale_channel_ids:
            closed_at = int(time.time())
            placeholders = ", ".join(["%s"] * len(stale_channel_ids))
            DatabasePool.execute(
                f"UPDATE tickets SET is_active = 0, closed_at = %s, reason = %s "
                f"WHERE channel_id IN ({placeholders}) AND is_active = 1",
                (closed_at, STALE_TICKET_REASON, *stale_channel_ids),
            )
            for channel_id in stale_channel_ids:
                active_ticket_cache.unregister(channel_id)

        return StaleTicketSyncResult(
            active_tickets_checked=len(rows),
            stale_channel_ids=stale_channel_ids,
        )
