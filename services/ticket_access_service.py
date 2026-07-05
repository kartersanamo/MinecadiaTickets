from __future__ import annotations

import discord

from core.config import ConfigManager
from core.loggers import log_tasks


class TicketAccessService:
    DRAFT_MAP_TICKET_TYPE = "Draft Map"

    @classmethod
    def draft_map_ticket_info(cls) -> dict:
        ticket_info = ConfigManager.tickets().get("Miscellaneous", {}).get(cls.DRAFT_MAP_TICKET_TYPE, {})
        return ticket_info if isinstance(ticket_info, dict) else {}

    @classmethod
    def draft_map_category_id(cls) -> int:
        return int(cls.draft_map_ticket_info().get("Category", 0) or 0)

    @classmethod
    def draft_map_user_ids(cls) -> list[int]:
        return cls._valid_ids(cls.draft_map_ticket_info().get("Users", []))

    @classmethod
    def _ticket_type_category_ids(cls) -> list[int]:
        category_ids: list[int] = []
        for category_tickets in ConfigManager.tickets().values():
            if not isinstance(category_tickets, dict):
                continue
            for ticket_info in category_tickets.values():
                if not isinstance(ticket_info, dict):
                    continue
                category_id = int(ticket_info.get("Category", 0) or 0)
                if category_id and category_id not in category_ids:
                    category_ids.append(category_id)
        return category_ids

    @classmethod
    def ticket_category_ids(cls) -> list[int]:
        category_ids = [int(category_id) for category_id in ConfigManager.get("TICKET_CATEGORIES", [])]
        for category_id in cls._ticket_type_category_ids():
            if category_id not in category_ids:
                category_ids.append(category_id)
        return category_ids

    @classmethod
    def is_ticket_category(cls, category_id: int | None) -> bool:
        return category_id is not None and category_id in cls.ticket_category_ids()

    @classmethod
    def resolve_category_id(cls, ticket_type_name: str, ticket_info: dict) -> int:
        return int(ticket_info.get("Category", 0) or 0)

    @classmethod
    def resolve_user_ids(cls, _ticket_type_name: str, ticket_info: dict) -> list[int]:
        return cls._valid_ids(ticket_info.get("Users", []))

    @classmethod
    def uses_user_only_access(cls, ticket_type_name: str, ticket_info: dict) -> bool:
        return bool(cls.resolve_user_ids(ticket_type_name, ticket_info)) and not ticket_info.get("Roles")

    @classmethod
    def _valid_ids(cls, values: object) -> list[int]:
        if not isinstance(values, list):
            return []
        user_ids: list[int] = []
        for value in values:
            try:
                user_id = int(value)
            except (TypeError, ValueError):
                continue
            if user_id > 0 and user_id not in user_ids:
                user_ids.append(user_id)
        return user_ids

    @classmethod
    async def fetch_members(cls, guild: discord.Guild, user_ids: list[int]) -> list[discord.Member]:
        members: list[discord.Member] = []
        for user_id in user_ids:
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except discord.HTTPException:
                    log_tasks.warning("Could not resolve guild member %s for ticket access", user_id)
                    continue
            members.append(member)
        return members

    @classmethod
    async def grant_user_channel_access(
        cls,
        channel: discord.TextChannel,
        user: discord.Member | discord.User,
        *,
        send_messages: bool = True,
    ) -> None:
        """Grant explicit channel access. Do not use overwrites_for() — inherit stays neutral."""
        await channel.set_permissions(
            user,
            overwrite=discord.PermissionOverwrite(
                view_channel=True,
                send_messages=send_messages,
                embed_links=True,
            ),
        )

    @classmethod
    async def grant_users_channel_access(
        cls,
        channel: discord.TextChannel,
        guild: discord.Guild,
        user_ids: list[int],
    ) -> list[discord.Member]:
        members = await cls.fetch_members(guild, user_ids)
        for member in members:
            await cls.grant_user_channel_access(channel, member)
        return members

    @classmethod
    async def grant_draft_map_configured_viewers(
        cls,
        channel: discord.TextChannel,
        guild: discord.Guild,
    ) -> list[discord.Member]:
        """Grant access to every user listed under Draft Map → Users in tickets.json."""
        return await cls.grant_users_channel_access(channel, guild, cls.draft_map_user_ids())

    @classmethod
    async def build_channel_overwrites(
        cls,
        guild: discord.Guild,
        ticket_type_name: str,
        ticket_info: dict,
        owner: discord.Member,
    ) -> dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite]:
        staff = guild.get_role(ConfigManager.get("ROLE_IDS")["STAFF_TEAM_ROLE_ID"])
        if staff is None:
            raise ValueError("Staff team role was not found")

        overwrites: dict[
            discord.Role | discord.Member | discord.Object,
            discord.PermissionOverwrite,
        ] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            owner: discord.PermissionOverwrite(view_channel=True, send_messages=False, embed_links=True),
            staff: discord.PermissionOverwrite(view_channel=False),
        }

        for role_id in ticket_info.get("Roles", []):
            role_obj = guild.get_role(int(role_id))
            if role_obj is not None:
                overwrites[role_obj] = discord.PermissionOverwrite(view_channel=True)

        viewer_ids = [user_id for user_id in cls.resolve_user_ids(ticket_type_name, ticket_info) if user_id != owner.id]
        viewers = await cls.fetch_members(guild, viewer_ids)
        for viewer in viewers:
            overwrites[viewer] = discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)

        return overwrites

    @classmethod
    async def mention_strings_for_ticket_open(
        cls,
        guild: discord.Guild,
        ticket_type_name: str,
        ticket_info: dict,
    ) -> list[str]:
        role_mentions = [
            role.mention
            for ping in ticket_info.get("Pings", [])
            if (role := guild.get_role(int(ping))) is not None
        ]
        if role_mentions:
            return role_mentions

        user_ids = cls.resolve_user_ids(ticket_type_name, ticket_info)
        if not user_ids:
            return []

        members = await cls.fetch_members(guild, user_ids)
        return [member.mention for member in members]

    @classmethod
    def validate_ticket_access_config(cls, ticket_type_name: str, ticket_info: dict) -> str | None:
        category_id = cls.resolve_category_id(ticket_type_name, ticket_info)
        if not category_id:
            if ticket_type_name == cls.DRAFT_MAP_TICKET_TYPE:
                return (
                    "`❌` Draft Map tickets are not configured yet. "
                    "Set `Category` for Draft Map in `assets/tickets.json`."
                )
            return "`❌` This ticket type does not have a valid category configured."

        if cls.uses_user_only_access(ticket_type_name, ticket_info):
            user_ids = cls.resolve_user_ids(ticket_type_name, ticket_info)
            if not user_ids:
                if ticket_type_name == cls.DRAFT_MAP_TICKET_TYPE:
                    return (
                        "`❌` Draft Map tickets are not configured yet. "
                        "Set `Users` for Draft Map in `assets/tickets.json`."
                    )
                return "`❌` This ticket type does not have any viewers configured."

        return None
