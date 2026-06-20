"""
analytics_tracking.py

This file is the cog for the analytics tracking.
It is used to track the analytics of the tickets in the server.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from core.analytics.logger import AnalyticsLogger as analytics
from core.bot_client import TicketsBot
from core.config import ConfigManager
from services.active_ticket_cache import active_ticket_cache


class TicketAnalytics(commands.Cog):
    def __init__(self, client: TicketsBot):
        self.client = client

    def _is_staff(self, member: discord.Member) -> bool:
        staff_role = ConfigManager.get("STAFF_ROLE_ID")
        if staff_role:
            role = member.guild.get_role(int(staff_role))
            if role and role in member.roles:
                return True
        return member.guild_permissions.manage_messages

    def _record_message(self, channel_id: int, *, is_staff: bool) -> None:
        analytics.record_ticket_message(str(channel_id), is_staff=is_staff)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        owner_id = active_ticket_cache.get_owner(message.channel.id)
        if not owner_id:
            return

        if not isinstance(message.author, discord.Member):
            return

        is_staff = self._is_staff(message.author)
        if str(message.author.id) == owner_id:
            is_staff = False

        asyncio.create_task(
            asyncio.to_thread(self._record_message, message.channel.id, is_staff=is_staff),
            name=f"ticket-analytics-{message.channel.id}",
        )


async def setup(client: TicketsBot) -> None:
    await client.add_cog(TicketAnalytics(client))
