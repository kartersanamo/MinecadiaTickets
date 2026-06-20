"""Local HTTP API for dashboard actions (close ticket, etc.)."""

from __future__ import annotations

import logging
import os

import discord
import requests
from aiohttp import web

from cogs.add import Add
from cogs.close import Close
from cogs.move import Move
from cogs.private import Private
from cogs.remove import Remove
from cogs.rename import Rename
from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool
from core.errors.exceptions import DISCORD_API_ERRORS, UI_CALLBACK_ERRORS, UserFacingError
from core.errors.messages import ErrorMessages

log = logging.getLogger("dashboard_http")


class DashboardHttp:
    _server: web.AppRunner | None = None

    @staticmethod
    def _api_secret() -> str | None:
        return os.environ.get("TICKETS_BOT_API_SECRET") or os.environ.get("CONTROL_API_SECRET")

    @staticmethod
    def _api_port() -> int:
        return int(os.environ.get("TICKETS_BOT_API_PORT", "8788"))

    def __init__(self, client: TicketsBot, secret: str) -> None:
        self._client = client
        self._secret = secret

    def _ticket_embed(self, description: str) -> discord.Embed:
        data = ConfigManager.all()
        embed = discord.Embed(
            description=description,
            color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
        )
        logo = data.get("LOGO")
        logo_url = None
        if isinstance(logo, str) and logo.startswith(("http://", "https://")):
            logo_url = logo
        embed.set_footer(text=data.get("FOOTER", "Minecadia Tickets Bot"), icon_url=logo_url)
        return embed

    @staticmethod
    def _extract_snowflake(raw: str) -> int | None:
        token = str(raw or "").strip()
        if token.startswith("<@") and token.endswith(">"):
            token = token[2:-1].lstrip("!")
        return int(token) if token.isdigit() else None

    async def close_ticket(self, request: web.Request) -> web.Response:
        if request.headers.get("X-Tickets-Key") != self._secret:
            return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            body = await request.json()
            channel_id = int(body["channel_id"])
            closed_by_id = int(body["closed_by_id"])
            reason = str(body.get("reason") or "").strip()
        except (KeyError, TypeError, ValueError):
            return web.json_response(
                {"error": "Invalid body (channel_id, closed_by_id, reason required)"},
                status=400,
            )

        if len(reason) < 2:
            return web.json_response({"error": "Reason must be at least 2 characters"}, status=400)

        guild_id = int(ConfigManager.get("GUILD_ID"))
        guild = self._client.get_guild(guild_id)
        if guild is None:
            return web.json_response({"error": "Guild not available"}, status=503)

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return web.json_response({"error": "Ticket channel not found"}, status=404)

        cog = self._client.get_cog("Close")
        if not isinstance(cog, Close):
            return web.json_response({"error": "Close cog not loaded"}, status=503)

        closer = guild.get_member(closed_by_id)
        if closer is None:
            try:
                closer = await guild.fetch_member(closed_by_id)
            except DISCORD_API_ERRORS:
                return web.json_response(
                    {
                        "error": "Staff member not found in guild — join the server with this Discord account",
                    },
                    status=400,
                )

        try:
            await cog.close_ticket_channel(guild, channel, closer, reason)
        except (UserFacingError, *UI_CALLBACK_ERRORS, requests.RequestException) as exc:
            log.exception("Dashboard close failed for %s", channel_id)
            return web.json_response({"error": ErrorMessages.user_message_for(exc)}, status=500)

        return web.json_response({"ok": True})

    async def execute_ticket_command(self, request: web.Request) -> web.Response:
        if request.headers.get("X-Tickets-Key") != self._secret:
            return web.json_response({"error": "Unauthorized"}, status=401)
        try:
            body = await request.json()
            channel_id = int(body["channel_id"])
            actor_id = int(body["actor_id"])
            command = str(body["command"]).strip().lower()
            args = str(body.get("args") or "").strip()
        except (KeyError, TypeError, ValueError):
            return web.json_response(
                {"error": "Invalid body (channel_id, actor_id, command, args)"},
                status=400,
            )

        guild = self._client.get_guild(int(ConfigManager.get("GUILD_ID")))
        if guild is None:
            return web.json_response({"error": "Guild not available"}, status=503)

        channel = guild.get_channel(channel_id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return web.json_response({"error": "Ticket channel not found"}, status=404)

        actor = guild.get_member(actor_id)
        if actor is None:
            try:
                actor = await guild.fetch_member(actor_id)
            except DISCORD_API_ERRORS:
                return web.json_response({"error": "Staff actor not found in guild"}, status=400)

        if channel.category is None or channel.category.id not in ConfigManager.get(
            "TICKET_CATEGORIES"
        ):
            return web.json_response({"error": "This channel is not a ticket"}, status=400)

        close_cog = self._client.get_cog("Close")
        rename_cog = self._client.get_cog("Rename")
        add_cog = self._client.get_cog("Add")
        remove_cog = self._client.get_cog("Remove")
        move_cog = self._client.get_cog("Move")
        private_cog = self._client.get_cog("Private")

        try:
            if command == "close":
                if not isinstance(close_cog, Close):
                    return web.json_response({"error": "Close cog not loaded"}, status=503)
                if len(args) < 2:
                    return web.json_response({"error": "Usage: /close <reason>"}, status=400)
                await close_cog.close_ticket_channel(guild, channel, actor, args)
                return web.json_response(
                    {"ok": True, "command": command, "detail": "Ticket closed"}
                )

            if command == "rename":
                if not isinstance(rename_cog, Rename):
                    return web.json_response({"error": "Rename cog not loaded"}, status=503)
                new_name = args.strip()
                if len(new_name) < 2:
                    return web.json_response(
                        {"error": "Usage: /rename <new-channel-name>"}, status=400
                    )
                old_name = channel.name
                await rename_cog.edit_channel_name(channel, new_name[:100])
                await channel.send(
                    embed=self._ticket_embed(
                        f"{actor.mention} has changed the ticket name from **{old_name}** to **{channel.name}**."
                    )
                )
                return web.json_response(
                    {"ok": True, "command": command, "detail": f"Renamed to {channel.name}"}
                )

            if command == "add":
                if not isinstance(add_cog, Add):
                    return web.json_response({"error": "Add cog not loaded"}, status=503)
                user_id = self._extract_snowflake(args)
                if not user_id:
                    return web.json_response(
                        {"error": "Usage: /add <user-id-or-mention>"}, status=400
                    )
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                if member is None:
                    return web.json_response({"error": "User not found"}, status=404)
                rows = DatabasePool.execute(
                    "SELECT 1 FROM blacklists WHERE user_id = %s LIMIT 1", (member.id,)
                )
                if rows:
                    return web.json_response({"error": "User is ticket blacklisted"}, status=400)
                if member.is_timed_out():
                    return web.json_response({"error": "User is timed out"}, status=400)
                await add_cog.set_permissions(channel, member)
                await channel.send(
                    embed=self._ticket_embed(
                        f"{actor.mention} has added {member.mention} to the ticket {channel.mention}"
                    )
                )
                return web.json_response(
                    {"ok": True, "command": command, "detail": f"Added {member.id}"}
                )

            if command == "remove":
                if not isinstance(remove_cog, Remove):
                    return web.json_response({"error": "Remove cog not loaded"}, status=503)
                user_id = self._extract_snowflake(args)
                if not user_id:
                    return web.json_response(
                        {"error": "Usage: /remove <user-id-or-mention>"}, status=400
                    )
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                if member is None:
                    return web.json_response({"error": "User not found"}, status=404)
                await remove_cog.remove_permissions(channel, member)
                await channel.send(
                    embed=self._ticket_embed(
                        f"{actor.mention} has removed {member.mention} from the ticket {channel.mention}"
                    )
                )
                return web.json_response(
                    {"ok": True, "command": command, "detail": f"Removed {member.id}"}
                )

            if command == "move":
                if not isinstance(move_cog, Move):
                    return web.json_response({"error": "Move cog not loaded"}, status=503)
                target = args.strip()
                if not target:
                    return web.json_response(
                        {"error": "Usage: /move <category-id-or-name>"}, status=400
                    )
                category = None
                if target.isdigit():
                    ch = guild.get_channel(int(target))
                    if isinstance(ch, discord.CategoryChannel):
                        category = ch
                if category is None:
                    lowered = target.lower()
                    for cat in guild.categories:
                        if cat.name.lower() == lowered:
                            category = cat
                            break
                if category is None:
                    return web.json_response({"error": "Target category not found"}, status=404)
                if category.id in ConfigManager.get("BLACKLISTED_MOVE_CATEGORIES"):
                    return web.json_response(
                        {"error": "You cannot move to this category"}, status=400
                    )
                if category.id not in ConfigManager.get("TICKET_CATEGORIES"):
                    return web.json_response({"error": "That is not a ticket category"}, status=400)
                original_overwrites = list(channel.overwrites.items())
                await channel.edit(category=category)
                await move_cog.update_database(category.name, channel.id)
                await channel.edit(sync_permissions=True)
                for key, value in original_overwrites:
                    if isinstance(key, (discord.Member, discord.Role)):
                        await channel.set_permissions(key, overwrite=value)
                staff_team = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
                if staff_team:
                    await channel.set_permissions(staff_team, view_channel=False)
                await channel.send(
                    embed=self._ticket_embed(
                        f"{actor.mention} has moved this ticket to **{category.name}**"
                    )
                )
                return web.json_response(
                    {"ok": True, "command": command, "detail": f"Moved to {category.name}"}
                )

            if command in ("private", "management"):
                if not isinstance(private_cog, Private):
                    return web.json_response({"error": "Private cog not loaded"}, status=503)
                if command == "private":
                    target_category = guild.get_channel(
                        ConfigManager.get("CHANNEL_IDS")["ADMIN+_CHECK_ID"]
                    )
                    privated = "Admin"
                    desc = "has turned this channel private."
                else:
                    target_category = guild.get_channel(
                        ConfigManager.get("CHANNEL_IDS")["MANAGEMENT_CONTACT_ID"]
                    )
                    privated = "Management"
                    desc = "has made this channel for management."
                if not isinstance(target_category, discord.CategoryChannel):
                    return web.json_response({"error": "Target category unavailable"}, status=503)
                previous_overwrites = list(channel.overwrites.items())
                await channel.edit(category=target_category)
                await private_cog.update_database(channel.id, privated)
                await channel.edit(sync_permissions=True)
                for key, value in previous_overwrites:
                    if isinstance(key, (discord.Member, discord.Role)):
                        await channel.set_permissions(key, overwrite=value)
                staff_team = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
                if staff_team:
                    await channel.set_permissions(staff_team, view_channel=False)
                await channel.send(embed=self._ticket_embed(f"{actor.mention} {desc}"))
                return web.json_response(
                    {"ok": True, "command": command, "detail": f"{command} applied"}
                )

            return web.json_response({"error": "Unknown ticket command"}, status=400)
        except (UserFacingError, *UI_CALLBACK_ERRORS, requests.RequestException) as exc:
            log.exception("Dashboard ticket-command failed for %s/%s", channel_id, command)
            return web.json_response({"error": ErrorMessages.user_message_for(exc)}, status=500)

    @classmethod
    async def start(cls, client: TicketsBot) -> None:
        secret = cls._api_secret()
        if not secret:
            log.warning(
                "TICKETS_BOT_API_SECRET / CONTROL_API_SECRET not set — dashboard close API disabled"
            )
            return

        async def health(_: web.Request) -> web.Response:
            return web.json_response({"ok": True})

        handler = cls(client, secret)
        app = web.Application()
        app.router.add_post("/close-ticket", handler.close_ticket)
        app.router.add_post("/ticket-command", handler.execute_ticket_command)
        app.router.add_get("/health", health)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", cls._api_port())
        await site.start()
        cls._server = runner
        log.info("Dashboard HTTP listening on 127.0.0.1:%s", cls._api_port())

    @classmethod
    async def stop(cls) -> None:
        if cls._server is not None:
            await cls._server.cleanup()
            cls._server = None
