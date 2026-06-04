"""
Ticket logs slash command — Components V2 browser for closed tickets.
"""
from __future__ import annotations

from discord import app_commands
from discord.enums import SeparatorSpacing
from discord.ext import commands
from typing import Any, Dict, List, Literal, Optional, Tuple
from datetime import datetime
import discord
import os
import pytz
from core.config import get_data
from core.database import execute
from core.decorators import task
from core.loggers import log_commands
from utils.embeds import get_embed_logo_url


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
    cfg = get_data()
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
    url = get_embed_logo_url(path)
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


class TicketLogUIState:
    __slots__ = ("target", "mode", "sort_key", "type_filter", "page", "detail_channel_id")

    def __init__(self, target: discord.Member) -> None:
        self.target = target
        self.mode: Literal["owner", "closer"] = "owner"
        self.sort_key: Literal["opened_at", "closed_at"] = "opened_at"
        self.type_filter: Optional[str] = None
        self.page: int = 0
        self.detail_channel_id: Optional[int] = None


class JumpTicketModal(discord.ui.Modal, title = "Jump to ticket #"):
    number = discord.ui.TextInput(
        label = "Ticket number",
        placeholder = "Digits from the ticket channel / log",
        min_length = 1,
        max_length = 32,
        required = True,
    )

    def __init__(self, state: TicketLogUIState) -> None:
        super().__init__(timeout = 300)
        self._state = state

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = (self.number.value or "").strip()
        row = _fetch_row_by_number(self._state.target.id, self._state.mode, raw)
        if not row:
            await interaction.response.send_message(
                f"No matching closed ticket **#{_truncate(raw, 32)}** for this perspective.",
                ephemeral = True,
            )
            return
        self._state.detail_channel_id = int(row["channelID"])
        self._state.page = 0
        view = TicketLogsV2Layout(interaction, self._state)
        kwargs: Dict[str, Any] = {"content": None, "view": view}
        if view._logo_files:
            kwargs["attachments"] = view._logo_files
        await interaction.response.edit_message(**kwargs)


class TicketLogsV2Layout(discord.ui.LayoutView):
    """Components V2 layout for /ticket-logs (list + detail + filters)."""

    def __init__(self, interaction: discord.Interaction, state: TicketLogUIState) -> None:
        super().__init__(timeout = 600)
        self.state = state
        cfg = get_data()
        self._logo_files, self._thumb = _logo_files_and_thumb(cfg)
        self._cfg = cfg
        rows = _fetch_rows(state.target.id, state.mode, state.sort_key, state.type_filter)
        self._rows = rows
        accent = _accent_int(cfg)
        inner: list = []

        if state.detail_channel_id is not None:
            self._build_detail(inner, interaction, accent)
        else:
            self._build_list(inner, interaction, accent, rows)

        self.add_item(discord.ui.Container(*inner, accent_color = accent))

    def _header_section(self, inner: list, title_md: str, interaction: discord.Interaction) -> None:
        if self._thumb:
            inner.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(title_md),
                    accessory = discord.ui.Thumbnail(self._thumb, description = (self._cfg.get("FOOTER") or "Logo")[:256]),
                )
            )
        else:
            inner.append(discord.ui.TextDisplay(title_md))

    def _build_detail(self, inner: list, interaction: discord.Interaction, accent: int) -> None:
        row = _row_by_channel(self._rows, self.state.detail_channel_id) or _fetch_row_by_channel(int(self.state.detail_channel_id))
        if not row:
            self._header_section(
                inner,
                "# Ticket details\n*That ticket could not be loaded. It may still be open or was removed.*",
                interaction,
            )
        else:
            title = f"# Ticket `#{_truncate(str(row.get('number') or ''), 24)}`\n*Full Record Below*"
            self._header_section(inner, title, interaction)
            inner.append(discord.ui.Separator(visible = True, spacing = SeparatorSpacing.large))
            for chunk in _format_detail_text(interaction, row):
                inner.append(discord.ui.TextDisplay(chunk))

        inner.append(discord.ui.Separator(visible = True, spacing = SeparatorSpacing.small))
        ar = discord.ui.ActionRow()
        ar.add_item(TLBackButton(self.state))
        show_t, _ = _staff_privacy(interaction, row) if row else (False, False)
        tr = (row.get("transcript") or "").strip() if row else ""
        if row and show_t and tr.startswith(("http://", "https://")):
            ar.add_item(discord.ui.Button(style = discord.ButtonStyle.link, label = "Transcript", url = tr))
        inner.append(ar)

    def _build_list(self, inner: list, interaction: discord.Interaction, accent: int, rows: List[Dict[str, Any]]) -> None:
        total = len(rows)
        max_page = max(0, (total - 1) // PAGE_SIZE) if total else 0
        if self.state.page > max_page:
            self.state.page = max_page

        title = (
            f"# Ticket Logs\n"
            f"Browsing **{self.state.target.display_name}** (`{self.state.target.id}`)\n"
            f"Use the menus to switch perspective, sort, and filter. Pick a row to see **details**."
        )
        self._header_section(inner, title, interaction)

        inner.append(discord.ui.ActionRow(TLModeSelect(self.state)))
        inner.append(discord.ui.ActionRow(TLSortSelect(self.state)))

        all_types = _distinct_types(_fetch_rows(self.state.target.id, self.state.mode, self.state.sort_key, None))
        if len(all_types) > 1:
            inner.append(discord.ui.ActionRow(TLTypeSelect(self.state, all_types[:24])))

        slice_rows = rows[self.state.page * PAGE_SIZE : self.state.page * PAGE_SIZE + PAGE_SIZE]
        inner.append(discord.ui.ActionRow(TLPickSelect(self.state, slice_rows, total)))

        page_count = max_page + 1 if total else 1
        inner.append(discord.ui.Separator(visible = True, spacing = SeparatorSpacing.small))
        for chunk in _build_page_quick_link_chunks(interaction, self.state, slice_rows, total, page_count, self._cfg):
            inner.append(discord.ui.TextDisplay(chunk))

        nav = discord.ui.ActionRow(
            TLPageButton("⏮", "first", self.state, disabled = self.state.page <= 0),
            TLPageButton("◀", "prev", self.state, disabled = self.state.page <= 0),
            TLPageButton("▶", "next", self.state, disabled = self.state.page >= max_page or total == 0),
            TLPageButton("⏭", "last", self.state, disabled = self.state.page >= max_page or total == 0),
            TLJumpButton(self.state),
        )
        inner.append(nav)

        inner.append(discord.ui.Separator(visible = True, spacing = SeparatorSpacing.small))
        inner.append(discord.ui.TextDisplay(f"{self._cfg.get('FOOTER', '')}"))

    @property
    def content_length_safe(self) -> int:
        try:
            return self.content_length()
        except Exception:
            return 0


def _row_by_channel(rows: List[Dict[str, Any]], channel_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if channel_id is None:
        return None
    for r in rows:
        try:
            if int(r["channelID"]) == int(channel_id):
                return r
        except (TypeError, ValueError, KeyError):
            continue
    return None


class TLModeSelect(discord.ui.Select):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(
            custom_id = "tl_v2_mode",
            placeholder = "Whose tickets?",
            min_values = 1,
            max_values = 1,
            options = [
                discord.SelectOption(
                    label = _truncate(f"Opened by {state.target.display_name}", 100),
                    value = "owner",
                    description = "They were the ticket owner",
                    default = state.mode == "owner",
                ),
                discord.SelectOption(
                    label = _truncate(f"Closed by {state.target.display_name}", 100),
                    value = "closer",
                    description = "They clicked close / closed the ticket",
                    default = state.mode == "closer",
                ),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self._state.mode = self.values[0]  # type: ignore[assignment]
        self._state.page = 0
        self._state.type_filter = None
        self._state.detail_channel_id = None
        await _tl_edit(interaction, self._state)


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


class TLTypeSelect(discord.ui.Select):
    """Option values are indices into ``self._types`` so long type names are not truncated."""

    def __init__(self, state: TicketLogUIState, types: List[str]) -> None:
        self._state = state
        self._types = types
        opts = [
            discord.SelectOption(label = "All types", value = "__all__", default = state.type_filter is None),
        ]
        for i, t in enumerate(types):
            opt_kw: Dict[str, Any] = {
                "label": _truncate(t, 100),
                "value": str(i),
                "default": state.type_filter == t,
            }
            if len(t) > 40:
                opt_kw["description"] = _truncate(t, 100)
            opts.append(discord.SelectOption(**opt_kw))
        super().__init__(
            custom_id = "tl_v2_type",
            placeholder = "Filter by ticket type…",
            min_values = 1,
            max_values = 1,
            options = opts[:25],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        v = self.values[0]
        if v == "__all__":
            self._state.type_filter = None
        else:
            self._state.type_filter = self._types[int(v)]
        self._state.page = 0
        self._state.detail_channel_id = None
        await _tl_edit(interaction, self._state)


class TLPickSelect(discord.ui.Select):
    def __init__(self, state: TicketLogUIState, slice_rows: List[Dict[str, Any]], total: int) -> None:
        self._state = state
        if not slice_rows:
            super().__init__(
                custom_id = "tl_v2_pick",
                placeholder = "No closed tickets in this view",
                min_values = 1,
                max_values = 1,
                options = [discord.SelectOption(label = "—", value = "__none__")],
                disabled = True,
            )
            return
        opts: List[discord.SelectOption] = []
        base = state.page * PAGE_SIZE
        for i, r in enumerate(slice_rows):
            idx = base + i + 1
            cid = int(r["channelID"])
            num = str(r.get("number") or "?")
            typ = (str(r.get("type") or "Unknown")).replace("\n", " ")
            name = (str(r.get("name") or "—")).replace("\n", " ")
            ts = _safe_int_ts(r.get(state.sort_key))
            label = _truncate(f"{idx}. #{num} · {typ} · {name}", 100)
            desc = _format_select_option_date(ts) if ts is not None else "Unknown date"
            opts.append(
                discord.SelectOption(
                    label = label,
                    value = str(cid),
                    description = _truncate(desc, 100),
                )
            )
        super().__init__(
            custom_id = "tl_v2_pick",
            placeholder = f"Open a ticket… ({total} total)",
            min_values = 1,
            max_values = 1,
            options = opts[:25],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.disabled or self.values[0] == "__none__":
            return
        self._state.detail_channel_id = int(self.values[0])
        await _tl_edit(interaction, self._state)


class TLPageButton(discord.ui.Button):
    def __init__(self, emoji: str, action: str, state: TicketLogUIState, *, disabled: bool) -> None:
        self._state = state
        self._action = action
        super().__init__(style = discord.ButtonStyle.secondary, emoji = emoji, custom_id = f"tl_pg_{action}", disabled = disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        rows = _fetch_rows(self._state.target.id, self._state.mode, self._state.sort_key, self._state.type_filter)
        total = len(rows)
        max_page = max(0, (total - 1) // PAGE_SIZE) if total else 0
        if self._action == "first":
            self._state.page = 0
        elif self._action == "prev":
            self._state.page = max(0, self._state.page - 1)
        elif self._action == "next":
            self._state.page = min(max_page, self._state.page + 1)
        else:
            self._state.page = max_page
        self._state.detail_channel_id = None
        await _tl_edit(interaction, self._state)


class TLJumpButton(discord.ui.Button):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(style = discord.ButtonStyle.primary, label = "Jump #", custom_id = "tl_v2_jump")

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(JumpTicketModal(self._state))


class TLBackButton(discord.ui.Button):
    def __init__(self, state: TicketLogUIState) -> None:
        self._state = state
        super().__init__(style = discord.ButtonStyle.primary, label = "← Back to list", custom_id = "tl_v2_back")

    async def callback(self, interaction: discord.Interaction) -> None:
        self._state.detail_channel_id = None
        await _tl_edit(interaction, self._state)


async def _tl_edit(interaction: discord.Interaction, state: TicketLogUIState) -> None:
    view = TicketLogsV2Layout(interaction, state)
    # Do not pass ``embed``/``embeds``: not allowed on messages with ``IS_COMPONENTS_V2``.
    kwargs: Dict[str, Any] = {"content": None, "view": view}
    if view._logo_files:
        kwargs["attachments"] = view._logo_files
    await interaction.response.edit_message(**kwargs)


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
                    accent_color = _accent_int(get_data()),
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

    @ticketlogs.error
    async def ticketlogs_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        if interaction.response.is_done():
            await interaction.followup.send(content = str(error), ephemeral = True)
        else:
            await interaction.response.send_message(content = str(error), ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketLogs(client))
