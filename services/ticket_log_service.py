"""Ticket log browser helpers (DB, formatting, privacy)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

import discord
import pytz

from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool


class TicketLogService:
    PAGE_SIZE = 25

    @staticmethod
    def safe_int_ts(raw: Any) -> Optional[int]:
        if raw is None or raw == "" or raw == " ":
            return None
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return None

    @classmethod
    def staff_privacy(cls, interaction: discord.Interaction, row: Dict[str, Any]) -> Tuple[bool, bool]:
        cfg = ConfigManager.all()
        guild = interaction.guild
        if guild is None:
            return False, False
        member = (
            interaction.user if isinstance(interaction.user, discord.Member) else guild.get_member(interaction.user.id)
        )
        if member is None:
            return False, False
        star = guild.get_role(int(cfg["ROLE_IDS"]["ADMINISTRATOR_PERMS_ROLE_ID"]))
        if star is not None and star in member.roles:
            return True, True
        priv = (row.get("privated") or "").strip()
        admin = any(role.id in cfg["ADMIN_ROLES"] for role in member.roles)
        mgmt = False
        if priv == "Admin" and not admin:
            return False, False
        if priv == "Management" and not mgmt:
            return False, False
        return True, True

    @classmethod
    def fetch_rows(
        cls,
        target_id: int,
        mode: Literal["owner", "closer"],
        sort_key: Literal["opened_at", "closed_at"],
        type_filter: Optional[str],
    ) -> List[Dict[str, Any]]:
        uid = int(target_id)
        order_col = "opened_at" if sort_key == "opened_at" else "closed_at"
        q = (
            "SELECT channel_id, number, name, type, transcript, reason, privated, "
            "closed_by_id, owner_id, opened_at, closed_at "
            "FROM tickets WHERE is_active = 0"
        )
        params: list[Any] = []
        if mode == "closer":
            q += " AND closed_by_id = %s"
            params.append(uid)
        else:
            q += " AND owner_id = %s"
            params.append(uid)
        if type_filter:
            q += " AND type = %s"
            params.append(type_filter)
        q += f" ORDER BY {order_col} DESC"
        return DatabasePool.execute(q, tuple(params)) or []

    @classmethod
    def fetch_row_by_channel(cls, channel_id: int) -> Optional[Dict[str, Any]]:
        rows = DatabasePool.execute(
            "SELECT channel_id, number, name, type, transcript, reason, privated, "
            "closed_by_id, owner_id, opened_at, closed_at "
            "FROM tickets WHERE channel_id = %s AND is_active = 0 LIMIT 1",
            (int(channel_id),),
        )
        return rows[0] if rows else None

    @classmethod
    def fetch_row_by_number(
        cls,
        target_id: int,
        mode: Literal["owner", "closer"],
        number: str,
    ) -> Optional[Dict[str, Any]]:
        uid = int(target_id)
        num = number.strip()
        if not num:
            return None
        q = (
            "SELECT channel_id, number, name, type, transcript, reason, privated, "
            "closed_by_id, owner_id, opened_at, closed_at "
            "FROM tickets WHERE is_active = 0 AND number = %s"
        )
        params: list[Any] = [num]
        if mode == "closer":
            q += " AND closed_by_id = %s"
            params.append(uid)
        else:
            q += " AND owner_id = %s"
            params.append(uid)
        rows = DatabasePool.execute(q + " LIMIT 1", tuple(params))
        return rows[0] if rows else None

    @staticmethod
    def distinct_types(rows: List[Dict[str, Any]]) -> List[str]:
        seen: List[str] = []
        for row in rows:
            ticket_type = (row.get("type") or "Unknown").strip()
            if ticket_type and ticket_type not in seen:
                seen.append(ticket_type)
        return sorted(seen, key=str.lower)

    @staticmethod
    def accent_int(cfg: dict) -> int:
        return discord.Color.from_str(cfg["EMBED_COLOR"]).value

    @classmethod
    def build_page_quick_link_chunks(
        cls,
        interaction: discord.Interaction,
        state: Any,
        slice_rows: List[Dict[str, Any]],
        _total: int,
        _page_count: int,
        _cfg: dict,
    ) -> List[str]:
        lines: List[str] = []
        base = state.page * cls.PAGE_SIZE
        for index, row in enumerate(slice_rows):
            idx = base + index + 1
            num = str(row.get("number") or "?")
            typ = cls.truncate(str(row.get("type") or "Unknown"), 56)
            name = cls.truncate(str(row.get("name") or "—"), 36)
            show_t, _ = cls.staff_privacy(interaction, row)
            transcript = (row.get("transcript") or "").strip()
            if show_t and transcript.startswith(("http://", "https://")):
                link = f"[Open transcript]({transcript})"
            elif not show_t:
                link = "*Transcript hidden (private ticket)*"
            else:
                link = "*No transcript URL*"
            lines.append(f"**{idx}.** `#{num}` · **{typ}** `{name}` {link}")
        body = "\n".join(lines) if lines else "*No closed tickets match this view on this page.*"
        return cls.chunk_text(body, 3400)

    @staticmethod
    def logo_files_and_thumb(
        interaction: discord.Interaction,
        cfg: dict,
    ) -> Tuple[List[discord.File], Optional[str]]:
        path = cfg.get("LOGO")
        client = interaction.client
        if not isinstance(client, TicketsBot):
            return [], None
        url = client.app.embeds.get_logo_url(path)
        files: List[discord.File] = []
        if not url:
            return [], None
        if url.startswith("attachment://") and path and os.path.isfile(path):
            fname = os.path.basename(path)
            files.append(discord.File(path, filename=fname))
            return files, f"attachment://{fname}"
        if url.startswith(("http://", "https://")):
            return [], url
        return [], None

    @staticmethod
    def truncate(value: str, max_len: int) -> str:
        value = value or ""
        return value if len(value) <= max_len else value[: max_len - 1] + "…"

    @staticmethod
    def ordinal_day(day: int) -> str:
        if 11 <= (day % 100) <= 13:
            return f"{day}th"
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{day}{suffix}"

    @classmethod
    def format_select_option_date(cls, ts: int) -> str:
        try:
            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(pytz.timezone("US/Eastern"))
        except (TypeError, ValueError, OSError):
            return "Unknown date"
        return f"{dt.strftime('%A')} {dt.strftime('%B')} {cls.ordinal_day(dt.day)}, {dt.year}"

    @staticmethod
    def chunk_text(text: str, max_chunk: int) -> List[str]:
        if len(text) <= max_chunk:
            return [text]
        return [text[i : i + max_chunk] for i in range(0, len(text), max_chunk)]

    @classmethod
    def format_detail_text(cls, interaction: discord.Interaction, row: Dict[str, Any]) -> List[str]:
        show_t, show_r = cls.staff_privacy(interaction, row)
        opened = cls.safe_int_ts(row.get("opened_at"))
        closed = cls.safe_int_ts(row.get("closed_at"))
        opened_s = f"<t:{opened}:F> (<t:{opened}:R>)" if opened else "`N/A`"
        closed_s = f"<t:{closed}:F> (<t:{closed}:R>)" if closed else "`N/A`"
        duration = "`N/A`"
        if opened and closed and closed >= opened:
            duration = f"`{closed - opened}s` (~{max(1, int((closed - opened) / 60))} min)"

        transcript = (row.get("transcript") or "").strip()
        if show_t and transcript:
            t_line = f"[Open transcript]({transcript})"
        elif not show_t:
            t_line = "*Transcript restricted (private ticket).*"
        else:
            t_line = "*No transcript link stored.*"

        reason = (row.get("reason") or "").strip() or "`N/A`"
        if not show_r:
            reason = "*Hidden (private ticket).*"

        priv = (row.get("privated") or "").strip() or "Public"
        closer_id = str(row.get("closed_by_id") or "").strip()
        closer_line = f"<@{closer_id}>" if closer_id.isdigit() else "`N/A`"
        owner_id = str(row.get("owner_id") or "").strip()
        owner_line = f"<@{owner_id}>" if owner_id.isdigit() else "`Unknown`"

        name = cls.truncate(str(row.get("name") or "unknown"), 200)
        typ = cls.truncate(str(row.get("type") or "Unknown"), 120)
        num = cls.truncate(str(row.get("number") or ""), 32)
        cid = str(row.get("channel_id") or "")

        block = (
            f"## Ticket `#{num}` — {typ}\n"
            f"**Channel ID:** `{cid}`\n"
            f"**Channel name (at close):** `{name}`\n"
            f"**Privacy:** `{priv}`\n\n"
            f"**Opened:** {opened_s}\n"
            f"**Closed:** {closed_s}\n"
            f"**Duration:** {duration}\n\n"
            f"**Owner:** {owner_line}\n"
            f"**Closed by:** {closer_line}\n\n"
            f"**Closure reason**\n{reason}\n\n"
            f"**Transcript**\n{t_line}"
        )
        return cls.chunk_text(block, 3800)

    @staticmethod
    def row_by_channel(
        rows: List[Dict[str, Any]],
        channel_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if channel_id is None:
            return None
        cid = int(channel_id)
        for row in rows:
            try:
                if int(row.get("channel_id") or 0) == cid:
                    return row
            except (TypeError, ValueError):
                continue
        return None
