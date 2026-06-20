"""Dashboard webhook notifications (avoids ticket_creation ↔ questions import cycle)."""

from __future__ import annotations

import asyncio
import os

import aiohttp
import discord

from core.loggers import log_tasks


async def notify_dashboard_new_ticket(
    channel: discord.TextChannel,
    number: int,
    ticket_type: str,
    owner_id: int,
) -> None:
    base_url = os.getenv("DASHBOARD_URL", "https://bots.kartersanamo.com").rstrip("/")
    endpoint = os.getenv("DASHBOARD_TICKET_NOTIFY_URL", "").strip() or f"{base_url}/api/tickets/live-events"
    secret = os.getenv("TICKETS_BOT_API_SECRET") or os.getenv("CONTROL_API_SECRET")
    if not endpoint or not secret:
        return

    payload = {
        "kind": "ticket_created",
        "channelId": str(channel.id),
        "ticketNumber": str(number),
        "ticketType": str(ticket_type),
        "ownerId": str(owner_id),
        "channelName": str(channel.name),
    }
    headers = {"X-Tickets-Key": secret, "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=2.5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    log_tasks.warning("Dashboard new-ticket notify failed (%s): %s", resp.status, body[:200])
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
        log_tasks.warning("Dashboard new-ticket notify error: %s", e)
