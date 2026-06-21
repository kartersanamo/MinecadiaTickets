"""Shared exception-type tuples (leaf module — no app imports)."""

from __future__ import annotations

import json
from typing import Tuple, Type

import discord

DISCORD_API_ERRORS: Tuple[Type[BaseException], ...] = (
    discord.HTTPException,
    discord.NotFound,
    discord.Forbidden,
)

CONFIG_IO_ERRORS: Tuple[Type[BaseException], ...] = (
    OSError,
    json.JSONDecodeError,
    KeyError,
    ValueError,
    TypeError,
)

UI_CALLBACK_ERRORS: Tuple[Type[BaseException], ...] = DISCORD_API_ERRORS + CONFIG_IO_ERRORS

MESSAGE_CONTENT_ERRORS: Tuple[Type[BaseException], ...] = (
    *DISCORD_API_ERRORS,
    ValueError,
    TypeError,
    AttributeError,
)

CHANNEL_HISTORY_ERRORS: Tuple[Type[BaseException], ...] = (*DISCORD_API_ERRORS, OSError)

DM_BROADCAST_ERRORS: Tuple[Type[BaseException], ...] = (
    *DISCORD_API_ERRORS,
    OSError,
    FileNotFoundError,
)
