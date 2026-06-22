"""Local HTTP API for dashboard actions (close ticket, etc.)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

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
from services.ticket_channel_ordering import TicketChannelOrdering

log = logging.getLogger("dashboard_http")


@dataclass(frozen=True)
class TicketCommandRequest:
    guild: discord.Guild
    channel: discord.TextChannel
    actor: discord.Member
    command: str
    args: str


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

    async def _fetch_guild_member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member is not None:
            return member
        try:
            return await guild.fetch_member(user_id)
        except *DISCORD_API_ERRORS:
            pass
        return None

    def _is_ticket_channel(self, channel: discord.TextChannel) -> bool:
        return channel.category is not None and channel.category.id in ConfigManager.get("TICKET_CATEGORIES")

    async def _restore_overwrites(
        self,
        channel: discord.TextChannel,
        overwrites: list[tuple[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite]],
    ) -> None:
        for key, value in overwrites:
            if isinstance(key, (discord.Member, discord.Role)):
                await channel.set_permissions(key, overwrite=value)
        staff_team = channel.guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        if staff_team:
            await channel.set_permissions(staff_team, view_channel=False)

    async def _cmd_close(self, req: TicketCommandRequest) -> web.Response:
        close_cog = self._client.get_cog("Close")
        if not isinstance(close_cog, Close):
            return web.json_response({"error": "Close cog not loaded"}, status=503)
        if len(req.args) < 2:
            return web.json_response({"error": "Usage: /close <reason>"}, status=400)
        await close_cog.close_ticket_channel(req.guild, req.channel, req.actor, req.args)
        return web.json_response({"ok": True, "command": req.command, "detail": "Ticket closed"})

    async def _cmd_rename(self, req: TicketCommandRequest) -> web.Response:
        rename_cog = self._client.get_cog("Rename")
        if not isinstance(rename_cog, Rename):
            return web.json_response({"error": "Rename cog not loaded"}, status=503)
        new_name = req.args.strip()
        if len(new_name) < 2:
            return web.json_response({"error": "Usage: /rename <new-channel-name>"}, status=400)
        old_name = req.channel.name
        await rename_cog.edit_channel_name(req.channel, new_name[:100])
        await req.channel.send(
            embed=self._ticket_embed(
                f"{req.actor.mention} has changed the ticket name from **{old_name}** to **{req.channel.name}**."
            )
        )
        return web.json_response(
            {"ok": True, "command": req.command, "detail": f"Renamed to {req.channel.name}"}
        )

    async def _cmd_add(self, req: TicketCommandRequest) -> web.Response:
        add_cog = self._client.get_cog("Add")
        if not isinstance(add_cog, Add):
            return web.json_response({"error": "Add cog not loaded"}, status=503)
        user_id = self._extract_snowflake(req.args)
        if not user_id:
            return web.json_response({"error": "Usage: /add <user-id-or-mention>"}, status=400)
        member = await self._fetch_guild_member(req.guild, user_id)
        if member is None:
            return web.json_response({"error": "User not found"}, status=404)
        rows = DatabasePool.execute("SELECT 1 FROM blacklists WHERE user_id = %s LIMIT 1", (member.id,))
        if rows:
            return web.json_response({"error": "User is ticket blacklisted"}, status=400)
        if member.is_timed_out():
            return web.json_response({"error": "User is timed out"}, status=400)
        await add_cog.set_permissions(req.channel, member)
        await req.channel.send(
            embed=self._ticket_embed(
                f"{req.actor.mention} has added {member.mention} to the ticket {req.channel.mention}"
            )
        )
        return web.json_response({"ok": True, "command": req.command, "detail": f"Added {member.id}"})

    async def _cmd_remove(self, req: TicketCommandRequest) -> web.Response:
        remove_cog = self._client.get_cog("Remove")
        if not isinstance(remove_cog, Remove):
            return web.json_response({"error": "Remove cog not loaded"}, status=503)
        user_id = self._extract_snowflake(req.args)
        if not user_id:
            return web.json_response({"error": "Usage: /remove <user-id-or-mention>"}, status=400)
        member = await self._fetch_guild_member(req.guild, user_id)
        if member is None:
            return web.json_response({"error": "User not found"}, status=404)
        await remove_cog.remove_permissions(req.channel, member)
        await req.channel.send(
            embed=self._ticket_embed(
                f"{req.actor.mention} has removed {member.mention} from the ticket {req.channel.mention}"
            )
        )
        return web.json_response({"ok": True, "command": req.command, "detail": f"Removed {member.id}"})

    def _resolve_move_category(self, guild: discord.Guild, target: str) -> discord.CategoryChannel | None:
        if target.isdigit():
            channel = guild.get_channel(int(target))
            if isinstance(channel, discord.CategoryChannel):
                return channel
        lowered = target.lower()
        for category in guild.categories:
            if category.name.lower() == lowered:
                return category
        return None

    async def _cmd_move(self, req: TicketCommandRequest) -> web.Response:
        move_cog = self._client.get_cog("Move")
        if not isinstance(move_cog, Move):
            return web.json_response({"error": "Move cog not loaded"}, status=503)
        target = req.args.strip()
        if not target:
            return web.json_response({"error": "Usage: /move <category-id-or-name>"}, status=400)
        category = self._resolve_move_category(req.guild, target)
        if category is None:
            return web.json_response({"error": "Target category not found"}, status=404)
        if category.id in ConfigManager.get("BLACKLISTED_MOVE_CATEGORIES"):
            return web.json_response({"error": "You cannot move to this category"}, status=400)
        if category.id not in ConfigManager.get("TICKET_CATEGORIES"):
            return web.json_response({"error": "That is not a ticket category"}, status=400)
        original_overwrites = list(req.channel.overwrites.items())
        position = TicketChannelOrdering.get_ticket_position(category, req.channel)
        await req.channel.edit(category=category, position=position)
        await move_cog.update_database(category.name, req.channel.id)
        await req.channel.edit(sync_permissions=True)
        await self._restore_overwrites(req.channel, original_overwrites)
        await req.channel.send(
            embed=self._ticket_embed(f"{req.actor.mention} has moved this ticket to **{category.name}**")
        )
        return web.json_response({"ok": True, "command": req.command, "detail": f"Moved to {category.name}"})

    async def _cmd_private(self, req: TicketCommandRequest) -> web.Response:
        private_cog = self._client.get_cog("Private")
        if not isinstance(private_cog, Private):
            return web.json_response({"error": "Private cog not loaded"}, status=503)
        if req.command == "private":
            target_category = req.guild.get_channel(ConfigManager.get("CHANNEL_IDS")["ADMIN+_CHECK_ID"])
            privated = "Admin"
            desc = "has turned this channel private."
        else:
            target_category = req.guild.get_channel(ConfigManager.get("CHANNEL_IDS")["MANAGEMENT_CONTACT_ID"])
            privated = "Management"
            desc = "has made this channel for management."
        if not isinstance(target_category, discord.CategoryChannel):
            return web.json_response({"error": "Target category unavailable"}, status=503)
        previous_overwrites = list(req.channel.overwrites.items())
        await req.channel.edit(category=target_category)
        await private_cog.update_database(req.channel.id, privated)
        await req.channel.edit(sync_permissions=True)
        await self._restore_overwrites(req.channel, previous_overwrites)
        await req.channel.send(embed=self._ticket_embed(f"{req.actor.mention} {desc}"))
        return web.json_response({"ok": True, "command": req.command, "detail": f"{req.command} applied"})

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

        closer = await self._fetch_guild_member(guild, closed_by_id)
        if closer is None:
            return web.json_response(
                {"error": "Staff member not found in guild — join the server with this Discord account"},
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

        actor = await self._fetch_guild_member(guild, actor_id)
        if actor is None:
            return web.json_response({"error": "Staff actor not found in guild"}, status=400)

        if not self._is_ticket_channel(channel):
            return web.json_response({"error": "This channel is not a ticket"}, status=400)

        req = TicketCommandRequest(guild=guild, channel=channel, actor=actor, command=command, args=args)
        handlers = {
            "close": self._cmd_close,
            "rename": self._cmd_rename,
            "add": self._cmd_add,
            "remove": self._cmd_remove,
            "move": self._cmd_move,
            "private": self._cmd_private,
            "management": self._cmd_private,
        }
        handler = handlers.get(command)
        if handler is None:
            return web.json_response({"error": "Unknown ticket command"}, status=400)

        try:
            return await handler(req)
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
