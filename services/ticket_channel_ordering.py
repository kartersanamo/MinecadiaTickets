from __future__ import annotations

import discord

from core.database import DatabasePool


class TicketChannelOrdering:
    """Sort ticket channels within categories (renamed top, un-renamed bottom)."""

    @staticmethod
    def ticket_sort_key(channel_name: str) -> tuple[int, str]:
        """Longest names first, then alphabetical."""
        return (-len(channel_name), channel_name.lower())

    @staticmethod
    def effective_channel_name(
        channel: discord.TextChannel,
        target_channel: discord.TextChannel,
        target_channel_name: str | None,
    ) -> str:
        if channel.id == target_channel.id and target_channel_name is not None:
            return target_channel_name
        return channel.name

    @staticmethod
    def is_unrenamed_ticket(channel_name: str, ticket_number: int | None) -> bool:
        """Original opened tickets use the `{username}-ticket-{number}` channel name format."""
        if ticket_number is None:
            return True
        return channel_name.endswith(f"-ticket-{ticket_number}")

    @classmethod
    def fetch_ticket_numbers(cls, channel_ids: list[int]) -> dict[int, int]:
        if not channel_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(channel_ids))
        rows = DatabasePool.execute(
            f"SELECT channel_id, number FROM tickets WHERE is_active = 1 AND channel_id IN ({placeholders})",
            tuple(channel_ids),
        )
        return {int(row["channel_id"]): int(row["number"]) for row in rows}

    @classmethod
    def count_position(
        cls,
        channels: list[discord.TextChannel],
        channel: discord.TextChannel,
        ticket_numbers: dict[int, int],
        *,
        channel_name: str | None,
    ) -> int:
        target_name = cls.effective_channel_name(channel, channel, channel_name)
        target_number = ticket_numbers.get(channel.id)
        target_is_unrenamed = cls.is_unrenamed_ticket(target_name, target_number)
        target_sort_key = cls.ticket_sort_key(target_name)

        renamed_before = 0
        unrenamed_before = 0
        renamed_count = 0

        for ticket_channel in channels:
            if ticket_channel.id == channel.id:
                continue

            resolved_name = cls.effective_channel_name(ticket_channel, channel, channel_name)
            ticket_number = ticket_numbers.get(ticket_channel.id)
            if cls.is_unrenamed_ticket(resolved_name, ticket_number):
                if target_is_unrenamed and resolved_name.lower() < target_name.lower():
                    unrenamed_before += 1
                continue

            renamed_count += 1
            if not target_is_unrenamed and cls.ticket_sort_key(resolved_name) < target_sort_key:
                renamed_before += 1

        if target_is_unrenamed:
            return renamed_count + unrenamed_before

        return renamed_before

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
        *,
        channel_name: str | None = None,
    ) -> int:
        """
        Guild position for a ticket channel after sorting inside its category.

        Renamed tickets are sorted at the top (longest name first, then alphabetical).
        Un-renamed tickets stay at the bottom of the category.
        """
        channels = sorted(category.text_channels, key=lambda ticket_channel: ticket_channel.position)
        ticket_numbers = cls.fetch_ticket_numbers([ticket_channel.id for ticket_channel in channels])
        category_index = cls.count_position(channels, channel, ticket_numbers, channel_name=channel_name)
        return cls.category_index_to_guild_position(category, channel, category_index)
