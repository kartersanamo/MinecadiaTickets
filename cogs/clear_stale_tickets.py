"""
clear_stale_tickets.py

Clears active ticket records whose Discord channels no longer exist.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.decorators import TaskDecorator
from core.discord_helpers import require_guild
from core.loggers import log_commands, log_tasks
from services.stale_ticket_service import StaleTicketService, StaleTicketSyncResult


class ClearStaleTickets(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client

    async def cog_load(self) -> None:
        if not self._hourly_sync.is_running():
            self._hourly_sync.start()

    async def cog_unload(self) -> None:
        self._hourly_sync.cancel()

    @classmethod
    def _log_sync_result(cls, result: StaleTicketSyncResult, source: str) -> None:
        if result.cleared_count:
            log_tasks.info(
                "%s: cleared %s stale ticket(s) from database (checked %s active): %s",
                source,
                result.cleared_count,
                result.active_tickets_checked,
                result.stale_channel_ids,
            )
            return

        log_tasks.info(
            "%s: no stale tickets found (%s active ticket(s) checked)",
            source,
            result.active_tickets_checked,
        )

    @classmethod
    def _run_sync(cls, guild: discord.Guild, source: str) -> StaleTicketSyncResult:
        result = StaleTicketService.clear_stale_tickets(guild)
        cls._log_sync_result(result, source)
        return result

    @tasks.loop(hours=1)
    async def _hourly_sync(self) -> None:
        guild = self.client.get_guild(ConfigManager.get("GUILD_ID"))
        if guild is None:
            log_tasks.warning("Clear stale tickets hourly sync skipped: guild not found")
            return
        self._run_sync(guild, "Clear stale tickets hourly sync")

    @_hourly_sync.before_loop
    async def _before_hourly_sync(self) -> None:
        await self.client.wait_until_ready()

    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.command(
        name="clearstaletickets",
        description="Marks active tickets as closed when their Discord channel no longer exists",
    )
    async def clearstaletickets(self, interaction: discord.Interaction) -> None:
        await self.clearstaletickets_command(interaction)

    @TaskDecorator.task("Clear Stale Tickets Command", True)
    async def clearstaletickets_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild = require_guild(interaction.guild)
        result = self._run_sync(guild, f"Clear stale tickets command ({interaction.user.id})")

        if result.cleared_count:
            description = (
                f"Cleared **{result.cleared_count}** stale ticket record(s).\n"
                f"Checked **{result.active_tickets_checked}** active ticket(s) in the database."
            )
        else:
            description = (
                f"No stale tickets found.\n"
                f"Checked **{result.active_tickets_checked}** active ticket(s) in the database."
            )

        embed = discord.Embed(
            title="Stale Ticket Sync",
            description=description,
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
        )
        if result.stale_channel_ids:
            channel_lines = "\n".join(f"`{channel_id}`" for channel_id in result.stale_channel_ids[:25])
            if len(result.stale_channel_ids) > 25:
                channel_lines += f"\n*...and {len(result.stale_channel_ids) - 25} more*"
            embed.add_field(name="Cleared Channel IDs", value=channel_lines, inline=False)

        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)
        await interaction.edit_original_response(embed=embed)
        log_commands.info(
            "%s (%s) ran /clearstaletickets: cleared %s stale ticket(s)",
            interaction.user,
            interaction.user.id,
            result.cleared_count,
        )


async def setup(client: TicketsBot) -> None:
    await client.add_cog(ClearStaleTickets(client))
