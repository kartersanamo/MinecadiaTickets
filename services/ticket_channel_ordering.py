from __future__ import annotations

import discord

from core.database import execute


def ticket_sort_key(channel: discord.TextChannel) -> tuple[int, str]:
    """Longest names first, then alphabetical."""
    return (-len(channel.name), channel.name.lower())


def is_unrenamed_ticket(channel_name: str, ticket_number: int | None) -> bool:
    """Original opened tickets use the `{username}-ticket-{number}` channel name format."""
    if ticket_number is None:
        return True
    return channel_name.endswith(f"-ticket-{ticket_number}")


def fetch_ticket_numbers(channel_ids: list[int]) -> dict[int, int]:
    if not channel_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(channel_ids))
    rows = execute(
        f"SELECT channel_id, number FROM tickets WHERE is_active = 1 AND channel_id IN ({placeholders})",
        tuple(channel_ids),
    )
    return {int(row["channel_id"]): int(row["number"]) for row in rows}


def get_ticket_position(category: discord.CategoryChannel, channel: discord.TextChannel) -> int:
    """
    Renamed tickets are sorted at the top (longest name first, then alphabetical).
    Un-renamed tickets stay at the bottom of the category.
    """
    channels = [existing for existing in category.text_channels if existing.id != channel.id] + [channel]
    ticket_numbers = fetch_ticket_numbers([ticket_channel.id for ticket_channel in channels])

    renamed_channels: list[discord.TextChannel] = []
    unrenamed_channels: list[discord.TextChannel] = []

    for ticket_channel in channels:
        ticket_number = ticket_numbers.get(ticket_channel.id)
        if is_unrenamed_ticket(ticket_channel.name, ticket_number):
            unrenamed_channels.append(ticket_channel)
        else:
            renamed_channels.append(ticket_channel)

    renamed_channels.sort(key=ticket_sort_key)
    unrenamed_channels.sort(key=lambda ticket_channel: ticket_channel.name.lower())

    ordered_channels = renamed_channels + unrenamed_channels
    return ordered_channels.index(channel)
