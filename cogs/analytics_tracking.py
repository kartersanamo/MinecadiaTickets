"""Track messages in open ticket channels (staff vs owner)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import discord
from discord.ext import commands

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _analytics import logger as analytics  # noqa: E402
from core.config import get_data
from services.active_ticket_cache import active_ticket_cache


def _record_message(channel_id: int, *, is_staff: bool) -> None:
    analytics.record_ticket_message(str(channel_id), is_staff=is_staff)


class TicketAnalytics(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.data = get_data()

    def _is_staff(self, member: discord.Member) -> bool:
        staff_role = self.data.get("STAFF_ROLE_ID")
        if staff_role:
            role = member.guild.get_role(int(staff_role))
            if role and role in member.roles:
                return True
        return member.guild_permissions.manage_messages

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        owner_id = active_ticket_cache.get_owner(message.channel.id)
        if not owner_id:
            return

        is_staff = self._is_staff(message.author)
        if str(message.author.id) == owner_id:
            is_staff = False

        asyncio.create_task(
            asyncio.to_thread(_record_message, message.channel.id, is_staff=is_staff),
            name=f"ticket-analytics-{message.channel.id}",
        )


async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketAnalytics(client))
