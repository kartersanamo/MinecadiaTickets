"""Track messages in open ticket channels (staff vs owner)."""
from __future__ import annotations

import sys
from pathlib import Path

import discord
from discord.ext import commands

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _analytics import logger as analytics  # noqa: E402
from Assets.functions import execute, get_data  # noqa: E402


class TicketAnalytics(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.data = get_data()
        self._ticket_cache: dict[int, tuple[str, float]] = {}

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
        channel_id = message.channel.id
        cached = self._ticket_cache.get(channel_id)
        if cached and cached[1] > discord.utils.utcnow().timestamp():
            owner_id, _ = cached
        else:
            rows = execute(
                f"SELECT ownerID FROM tickets WHERE channelID = '{channel_id}' "
                "AND active = 'True' LIMIT 1"
            )
            if not rows:
                self._ticket_cache.pop(channel_id, None)
                return
            owner_id = str(rows[0]["ownerID"])
            self._ticket_cache[channel_id] = (
                owner_id,
                discord.utils.utcnow().timestamp() + 120,
            )

        is_staff = self._is_staff(message.author)
        if str(message.author.id) == owner_id:
            is_staff = False
        analytics.record_ticket_message(str(channel_id), is_staff=is_staff)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketAnalytics(client))
