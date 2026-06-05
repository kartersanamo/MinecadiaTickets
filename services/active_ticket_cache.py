from __future__ import annotations

import asyncio
import logging
from typing import Optional

from discord.ext import commands, tasks

from core.database import aexecute

log = logging.getLogger("Tasks")


class ActiveTicketCache:
    """In-memory map of open ticket channel_id -> owner_id. Avoids per-message DB lookups."""

    def __init__(self) -> None:
        self._channels: dict[int, str] = {}
        self._lock = asyncio.Lock()

    def get_owner(self, channel_id: int) -> Optional[str]:
        return self._channels.get(channel_id)

    def register(self, channel_id: int, owner_id: int | str) -> None:
        self._channels[int(channel_id)] = str(owner_id)

    def unregister(self, channel_id: int) -> None:
        self._channels.pop(int(channel_id), None)

    async def refresh(self) -> None:
        rows = await aexecute(
            "SELECT channel_id, owner_id FROM tickets WHERE is_active = %s",
            (1,),
        )
        parsed: dict[int, str] = {}
        for row in rows:
            try:
                parsed[int(row["channel_id"])] = str(row["owner_id"])
            except (KeyError, TypeError, ValueError):
                continue
        async with self._lock:
            self._channels = parsed
        log.debug("Active ticket cache refreshed (%s channels)", len(parsed))


active_ticket_cache = ActiveTicketCache()


class ActiveTicketCacheCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        await active_ticket_cache.refresh()
        if not self._refresh_loop.is_running():
            self._refresh_loop.start()

    def cog_unload(self) -> None:
        self._refresh_loop.cancel()

    @tasks.loop(minutes=2)
    async def _refresh_loop(self) -> None:
        await active_ticket_cache.refresh()

    @_refresh_loop.before_loop
    async def _before_refresh(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActiveTicketCacheCog(bot))
