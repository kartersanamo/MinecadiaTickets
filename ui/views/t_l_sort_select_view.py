"""
Ticket logs slash command — Components V2 browser for closed tickets.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple
from datetime import datetime
import discord
import os
import pytz
from core.config import ConfigManager
from core.database import execute
from ui.views.ticket_log_u_i_state_view import TicketLogUIState
from ui.views.ticket_logs_v2_support import _tl_edit


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
        "SELECT channelID, number, name, type, transcript, reason, privated, closed_by, ownerID, opened_at, closed_at "
        "FROM tickets WHERE active = 'False'"
    )
    if mode == "closer":
        q += f" AND closed_by = '{uid}'"
    else:
        q += f" AND ownerID = '{uid}'"
    if type_filter:
        q += f" AND type = '{_sql_escape(type_filter)}'"
    q += f" ORDER BY {order_col} DESC"
    return execute(q) or []


def _fetch_row_by_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    rows = execute(
        "SELECT channelID, number, name, type, transcript, reason, privated, closed_by, ownerID, opened_at, closed_at "
        f"FROM tickets WHERE channelID = '{int(channel_id)}' AND active = 'False' LIMIT 1"
    )
    return rows[0] if rows else None


def _fetch_row_by_number(
    target_id: int,
    mode: Literal["owner", "closer"],
    number: str,
) -> Optional[Dict[str, Any]]:
    uid = int(target_id)
    num = _sql_escape(number.strip())
    if not num:
        return None
    q = (
        "SELECT channelID, number, name, type, transcript, reason, privated, closed_by, ownerID, opened_at, closed_at "
        "FROM tickets WHERE active = 'False' AND number = '" + num + "'"
    )
    if mode == "closer":
        q += f" AND closed_by = '{uid}'"
    else:
        q += f" AND ownerID = '{uid}'"
    rows = execute(q + " LIMIT 1")
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
    url = interaction.client.app.embeds.get_logo_url(path)
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
    closer_id = str(row.get("closed_by") or "").strip()
    closer_line = f"<@{closer_id}>" if closer_id.isdigit() else "`N/A`"
    owner_id = str(row.get("ownerID") or "").strip()
    owner_line = f"<@{owner_id}>" if owner_id.isdigit() else "`Unknown`"

    name = _truncate(str(row.get("name") or "unknown"), 200)
    typ = _truncate(str(row.get("type") or "Unknown"), 120)
    num = _truncate(str(row.get("number") or ""), 32)
    cid = str(row.get("channelID") or "")

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


class TLSortSelect(discord.ui.Select):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(
            custom_id = "tl_v2_sort",
            placeholder = "Sort by…",
            min_values = 1,
            max_values = 1,
            options = [
                discord.SelectOption(
                    label = "Opened at (newest)",
                    value = "opened_at",
                    default = state.sort_key == "opened_at",
                ),
                discord.SelectOption(
                    label = "Closed at (newest)",
                    value = "closed_at",
                    default = state.sort_key == "closed_at",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self._state.sort_key = self.values[0]  # type: ignore[assignment]
        self._state.page = 0
        self._state.detail_channel_id = None
        await _tl_edit(interaction, self._state)
