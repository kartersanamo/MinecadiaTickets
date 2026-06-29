"""
activetickets.py

This file is the cog for the active tickets command.
It is used to display the tickets that the user is actively speaking in.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

import asyncio
import os
from typing import List, Optional, Tuple

import cachetools
import discord
from discord import app_commands
from discord.enums import SeparatorSpacing
from discord.ext import commands

from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.decorators import TaskDecorator
from core.discord_helpers import require_guild
from core.errors.exceptions import CHANNEL_HISTORY_ERRORS
from core.loggers import log_tasks
from services.ticket_access_service import TicketAccessService


class ActiveTickets(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client
        self.cache = cachetools.TTLCache(
            maxsize=ConfigManager.get("ACTIVE_TICKETS_CACHE")["ENTRIES"],
            ttl=60 * ConfigManager.get("ACTIVE_TICKETS_CACHE")["MINUTES_TO_EXPIRE"],
        )

    @TaskDecorator.task("Check User Messages")
    async def check_user_messages(self, user_id: int, channel: discord.TextChannel, tickets: list) -> None:
        cache_key: str = f"{user_id}-{channel.id}"
        if cache_key in self.cache:
            if self.cache[cache_key]:
                tickets.append((channel.mention, channel.category.name if channel.category else "Unknown"))
            return

        try:
            async for message in channel.history(limit=None):
                if message.author.id == user_id:
                    tickets.append((channel.mention, channel.category.name if channel.category else "Unknown"))
                    self.cache[cache_key] = True
                    return
            self.cache[cache_key] = False

        except CHANNEL_HISTORY_ERRORS as error:
            log_tasks.error("Checking user messages error %s", error)
            self.cache[cache_key] = False

    @TaskDecorator.task("Get Tickets", True)
    async def get_tickets_list(self, interaction: discord.Interaction) -> List[Tuple[str, str]]:
        tickets: List[Tuple[str, str]] = []
        guild = require_guild(interaction.guild)
        if not isinstance(interaction.user, discord.Member):
            return tickets
        member = interaction.user
        for category_id in TicketAccessService.ticket_category_ids():
            category = guild.get_channel(category_id)
            if isinstance(category, discord.CategoryChannel):
                tasks = [
                    asyncio.create_task(self.check_user_messages(member.id, ticket, tickets))
                    for ticket in category.text_channels
                    if ticket.permissions_for(member).read_messages
                ]
                await asyncio.gather(*tasks)

        return tickets

    @staticmethod
    def _chunk_line_blocks(lines: List[str], max_chunk: int) -> List[str]:
        blocks: List[str] = []
        cur: List[str] = []
        size = 0
        for line in lines:
            add = len(line) + (1 if cur else 0)
            if cur and size + add > max_chunk:
                blocks.append("\n".join(cur))
                cur = [line]
                size = len(line)
            else:
                cur.append(line)
                size += add
        if cur:
            blocks.append("\n".join(cur))
        return blocks

    @staticmethod
    def _active_tickets_title(interaction: discord.Interaction, tickets: List[Tuple[str, str]]) -> str:
        title = (
            "# Active Tickets\n"
            f"Tickets where **{interaction.user.mention}** has sent at least one message."
        )
        if tickets:
            suffix = "s" if len(tickets) != 1 else ""
            title += f"\n\n**{len(tickets)}** open channel{suffix}."
        else:
            title += "\n\n*You are not active in any ticket channels right now.*"
        return title

    @staticmethod
    def _logo_thumbnail(
        logo_path: str | None, logo_url: str | None
    ) -> Tuple[List[discord.File], Optional[str], bool]:
        logo_files: List[discord.File] = []
        if not logo_url:
            return logo_files, None, False
        if logo_url.startswith("attachment://") and logo_path and os.path.isfile(logo_path):
            fname = os.path.basename(logo_path)
            logo_files.append(discord.File(logo_path, filename=fname))
            return logo_files, f"attachment://{fname}", True
        if logo_url.startswith(("http://", "https://")):
            return logo_files, logo_url, True
        return logo_files, None, False

    def _build_active_tickets_layout(
        self, interaction: discord.Interaction, tickets: List[Tuple[str, str]]
    ) -> Tuple[discord.ui.LayoutView, List[discord.File]]:
        accent = discord.Color.from_str(ConfigManager.get("EMBED_COLOR"))
        logo_path = ConfigManager.get("LOGO")
        logo_url = self.client.app.embeds.get_logo_url(logo_path)
        logo_files, thumb_media, use_section = self._logo_thumbnail(logo_path, logo_url)
        title_block = self._active_tickets_title(interaction, tickets)
        thumb_desc = (ConfigManager.get("FOOTER") or "Logo")[:256]

        view = discord.ui.LayoutView(timeout=None)
        inner: list = []

        if use_section and thumb_media:
            inner.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(title_block),
                    accessory=discord.ui.Thumbnail(thumb_media, description=thumb_desc),
                )
            )
        else:
            inner.append(discord.ui.TextDisplay(title_block))

        inner.append(discord.ui.Separator(visible=True, spacing=SeparatorSpacing.large))

        if tickets:
            lines = []
            for mention, cat in tickets:
                safe_cat = cat.replace("`", "'")
                lines.append(f"- {mention} — `{safe_cat}`")
            for block in self._chunk_line_blocks(lines, 3500):
                inner.append(discord.ui.TextDisplay(block))

        inner.append(discord.ui.Separator(visible=True, spacing=SeparatorSpacing.small))
        inner.append(discord.ui.TextDisplay(f"{ConfigManager.get('FOOTER')}"))

        container = discord.ui.Container(*inner, accent_color=accent)
        view.add_item(container)

        if view.content_length() > 4000:
            fallback = discord.ui.LayoutView(timeout=None)
            fallback.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(
                        "# Active Tickets\n"
                        "Your ticket list is too long to display here. "
                        "Please narrow your open tickets or ask staff for help."
                    ),
                    accent_color=accent,
                )
            )
            return fallback, []
        return view, logo_files

    @TaskDecorator.task("Send Components V2 response")
    async def send_active_tickets_response(
        self, interaction: discord.Interaction, tickets: List[Tuple[str, str]]
    ) -> None:
        view, logo_files = self._build_active_tickets_layout(interaction, tickets)
        edit_kw: dict = {"content": None, "embed": None, "view": view}
        if logo_files:
            edit_kw["attachments"] = logo_files
        await interaction.edit_original_response(**edit_kw)

    @app_commands.guild_only()
    @app_commands.command(name="active-tickets", description="Returns which tickets you are actively speaking in")
    async def activetickets(self, interaction: discord.Interaction) -> None:
        await self.activetickets_command(interaction)

    @TaskDecorator.task("ActiveTickets Command", True)
    async def activetickets_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        tickets: List[Tuple[str, str]] = await self.get_tickets_list(interaction)
        await self.send_active_tickets_response(interaction, tickets)


async def setup(client: TicketsBot) -> None:
    await client.add_cog(ActiveTickets(client))
