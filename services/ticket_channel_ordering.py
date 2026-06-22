from __future__ import annotations

import discord

from core.database import DatabasePool


class TicketChannelOrdering:
    """Place ticket channels oldest-first within a category (by opened_at)."""

    @classmethod
    def fetch_opened_at(cls, channel_ids: list[int]) -> dict[int, float]:
        if not channel_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(channel_ids))
        rows = DatabasePool.execute(
            f"SELECT channel_id, opened_at FROM tickets WHERE is_active = 1 AND channel_id IN ({placeholders})",
            tuple(channel_ids),
        )
        return {int(row["channel_id"]): float(row["opened_at"]) for row in rows}

    @classmethod
    def count_position(
        cls,
        channels: list[discord.TextChannel],
        channel: discord.TextChannel,
        opened_at: dict[int, float],
    ) -> int:
        target_ts = opened_at.get(channel.id, float("inf"))
        target_id = channel.id
        before = 0
        for ticket_channel in channels:
            if ticket_channel.id == channel.id:
                continue
            peer_ts = opened_at.get(ticket_channel.id, float("inf"))
            if peer_ts < target_ts or (peer_ts == target_ts and ticket_channel.id < target_id):
                before += 1
        return before

    @staticmethod
    def category_index_to_guild_position(
        category: discord.CategoryChannel,
        channel: discord.TextChannel,
        category_index: int,
    ) -> int:
        """Map a 0-based index inside the category to Discord's guild-wide position value."""
        peers = sorted(
            (peer for peer in category.text_channels if peer.id != channel.id),
            key=lambda peer: peer.position,
        )
        if not peers:
            return category.position + 1
        if category_index <= 0:
            return peers[0].position
        if category_index >= len(peers):
            return peers[-1].position + 1
        return peers[category_index].position

    @classmethod
    def get_ticket_position(
        cls,
        category: discord.CategoryChannel,
        channel: discord.TextChannel,
    ) -> int:
        """Guild position for a ticket channel sorted oldest-first by opened_at."""
        channels = sorted(category.text_channels, key=lambda ticket_channel: ticket_channel.position)
        channel_ids = [ticket_channel.id for ticket_channel in channels]
        if channel.id not in channel_ids:
            channel_ids.append(channel.id)
        opened_at = cls.fetch_opened_at(channel_ids)
        category_index = cls.count_position(channels, channel, opened_at)
        return cls.category_index_to_guild_position(category, channel, category_index)
