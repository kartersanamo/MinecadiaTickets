"""Small helpers for narrowing Discord API types in slash-command handlers."""

from __future__ import annotations

import discord


def require_guild(guild: discord.Guild | None) -> discord.Guild:
    if guild is None:
        raise ValueError("Guild is required")
    return guild


def require_text_channel(channel: object | None) -> discord.TextChannel:
    if not isinstance(channel, discord.TextChannel):
        raise TypeError("Expected a text channel")
    return channel


def require_category_channel(
    channel: discord.abc.GuildChannel | None,
) -> discord.CategoryChannel:
    if not isinstance(channel, discord.CategoryChannel):
        raise TypeError("Expected a category channel")
    return channel


def require_member(
    user: discord.User | discord.Member | None,
) -> discord.Member:
    if not isinstance(user, discord.Member):
        raise TypeError("Expected a guild member")
    return user
