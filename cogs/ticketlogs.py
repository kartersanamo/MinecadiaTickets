"""
Ticket logs slash command — Components V2 browser for closed tickets.
"""
from __future__ import annotations

from discord import app_commands
from discord.ext import commands
from typing import Any, Dict, List, Literal, Optional, Tuple
from datetime import datetime
import discord
import os
import pytz
from core.config import ConfigManager
from core.database import execute
from core.decorators import task


PAGE_SIZE = 25


def _sql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''")


def _safe_int_ts(raw: Any) -> Optional[int]:
    if raw is None or raw == "" or raw == " ":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _staff_privacy(interaction: discord.Interaction, row: Dict[str, Any]) -> Tuple[bool, bool]:
    cfg = ConfigManager.all()
    star = interaction.guild.get_role(cfg["ROLE_IDS"]["ADMINISTRATOR_PERMS_ROLE_ID"])
    if star is not None and star in interaction.user.roles:
        # Administrator perms role bypasses all private-ticket redaction.
        return True, True
    priv = (row.get("privated") or "").strip()
    admin = any(role.id in cfg["ADMIN_ROLES"] for role in interaction.user.roles)
    # Star role already returned; only that role bypasses Management-private below.
    mgmt = False
    if priv == "Admin" and not admin:
        return False, False
    if priv == "Management" and not mgmt:
        return False, False
    return True, True


def _fetch_rows(
    target_id: int,
    mode: Literal["owner", "closer"],
    sort_key: Literal["opened_at", "closed_at"],
    type_filter: Optional[str],
) -> List[Dict[str, Any]]:
    uid = int(target_id)
    order_col = "opened_at" if sort_key == "opened_at" else "closed_at"
    q = (
        "SELECT channel_id, number, name, type, transcript, reason, privated, closed_by_id, owner_id, opened_at, closed_at "
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
    return execute(q, tuple(params)) or []


def _fetch_row_by_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    rows = execute(
        "SELECT channel_id, number, name, type, transcript, reason, privated, closed_by_id, owner_id, opened_at, closed_at "
        "FROM tickets WHERE channel_id = %s AND is_active = 0 LIMIT 1",
        (int(channel_id),),
    )
    return rows[0] if rows else None


def _fetch_row_by_number(
    target_id: int,
    mode: Literal["owner", "closer"],
    number: str,
) -> Optional[Dict[str, Any]]:
    uid = int(target_id)
    num = number.strip()
    if not num:
        return None
    q = (
        "SELECT channel_id, number, name, type, transcript, reason, privated, closed_by_id, owner_id, opened_at, closed_at "
        "FROM tickets WHERE is_active = 0 AND number = %s"
    )
    params: list[Any] = [num]
    if mode == "closer":
        q += " AND closed_by_id = %s"
        params.append(uid)
    else:
        q += " AND owner_id = %s"
        params.append(uid)
    rows = execute(q + " LIMIT 1", tuple(params))
    return rows[0] if rows else None


def _distinct_types(rows: List[Dict[str, Any]]) -> List[str]:
    seen: List[str] = []
    for r in rows:
        t = (r.get("type") or "Unknown").strip()
        if t and t not in seen:
            seen.append(t)
    return sorted(seen, key = str.lower)


def _accent_int(cfg: dict) -> int:
    return discord.Color.from_str(cfg["EMBED_COLOR"]).value


def _build_page_quick_link_chunks(
    interaction: discord.Interaction,
    state: TicketLogUIState,
    slice_rows: List[Dict[str, Any]],
    total: int,
    page_count: int,
    cfg: dict,
) -> List[str]:
    lines: List[str] = []
    base = state.page * PAGE_SIZE
    for i, row in enumerate(slice_rows):
        idx = base + i + 1
        num = str(row.get("number") or "?")
        typ = _truncate(str(row.get("type") or "Unknown"), 56)
        name = _truncate(str(row.get("name") or "—"), 36)
        show_t, _ = _staff_privacy(interaction, row)
        tr = (row.get("transcript") or "").strip()
        if show_t and tr.startswith(("http://", "https://")):
            link = f"[Open transcript]({tr})"
        elif not show_t:
            link = "*Transcript hidden (private ticket)*"
        else:
            link = "*No transcript URL*"
        lines.append(f"**{idx}.** `#{num}` · **{typ}** `{name}` {link}")
    if not lines:
        body = "*No closed tickets match this view on this page.*"
    else:
        body = "\n".join(lines)
    return _chunk_text(body, 3400)


def _logo_files_and_thumb(cfg: dict) -> Tuple[List[discord.File], Optional[str]]:
    path = cfg.get("LOGO")
    url = self.client.app.embeds.get_logo_url(path)
    files: List[discord.File] = []
    if not url:
        return [], None
    if url.startswith("attachment://") and path and os.path.isfile(path):
        fname = os.path.basename(path)
        files.append(discord.File(path, filename = fname))
        return files, f"attachment://{fname}"
    if url.startswith(("http://", "https://")):
        return [], url
    return [], None


def _truncate(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _ordinal_day(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _format_select_option_date(ts: int) -> str:
    try:
        dt = datetime.fromtimestamp(int(ts), tz = pytz.UTC).astimezone(pytz.timezone("US/Eastern"))
    except (TypeError, ValueError, OSError):
        return "Unknown date"
    return f"{dt.strftime('%A')} {dt.strftime('%B')} {_ordinal_day(dt.day)}, {dt.year}"


def _chunk_text(text: str, max_chunk: int) -> List[str]:
    if len(text) <= max_chunk:
        return [text]
    return [text[i : i + max_chunk] for i in range(0, len(text), max_chunk)]


def _format_detail_text(interaction: discord.Interaction, row: Dict[str, Any]) -> List[str]:
    show_t, show_r = _staff_privacy(interaction, row)
    opened = _safe_int_ts(row.get("opened_at"))
    closed = _safe_int_ts(row.get("closed_at"))
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

    name = _truncate(str(row.get("name") or "unknown"), 200)
    typ = _truncate(str(row.get("type") or "Unknown"), 120)
    num = _truncate(str(row.get("number") or ""), 32)
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
    return _chunk_text(block, 3800)
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_layout_view import TicketLogsV2Layout

class TicketLogs(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client = client

    @task("Ticket Logs Command", True)
    async def ticket_logs_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await interaction.response.defer()
        state = TicketLogUIState(user)
        view = TicketLogsV2Layout(interaction, state)
        kwargs: Dict[str, Any] = {"content": None, "view": view}
        if view._logo_files:
            kwargs["attachments"] = view._logo_files
        if view.content_length_safe > 4000:
            fb = discord.ui.LayoutView(timeout = 600)
            fb.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(
                        "# Ticket Logs\n"
                        "This response would exceed Discord limits. "
                        "Try a **type filter** or the other **perspective** to narrow results."
                    ),
                    accent_color = _accent_int(ConfigManager.all()),
                )
            )
            await interaction.edit_original_response(content = None, view = fb)
            return
        await interaction.edit_original_response(**kwargs)

    @app_commands.guild_only()
    @app_commands.command(name = "ticket-logs", description = "Browse closed tickets for a member (Components V2)")
    @app_commands.describe(user = "Member to look up")
    async def ticketlogs(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await self.ticket_logs_command(interaction, user)



async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketLogs(client))
