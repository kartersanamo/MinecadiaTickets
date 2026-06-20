"""
close.py

This file is the cog for the close command.
It is used to close a ticket channel and generate a transcript.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

import asyncio
import datetime
import time

import discord
import pytz
import requests
from discord import app_commands
from discord.ext import commands

from core.analytics.logger import AnalyticsLogger as analytics
from core.bot_client import TicketsBot
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.discord_helpers import require_guild, require_member, require_text_channel
from core.errors.exceptions import DISCORD_API_ERRORS
from core.loggers import log_commands, log_tasks
from services.statistics_service import is_found
from services.ticket_check_service import is_ticket


class Close(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client

    def convert_to_est(self, timestamp: int | float | str) -> str:
        try:
            est_time = datetime.datetime.fromtimestamp(int(float(timestamp)), tz=pytz.utc).astimezone(
                pytz.timezone("US/Eastern")
            )
            return est_time.strftime("%a, %b %d, %Y, %I:%M:%S %p") + " EST"

        except (ValueError, TypeError, OSError) as error:
            log_commands.warning("Failed to convert the timestamp to EST %s", error)
            return "N/A"

    @TaskDecorator.task("Get Transcript Link")
    async def return_link(self, content) -> str:
        url: str = "https://paste.minecadia.com/documents"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(url, headers=headers, data=content.encode("utf-8"), timeout=30)
        response_data = response.json()
        key = response_data["key"]
        return f"https://paste.minecadia.com/{key}"

        # url: str = 'https://paste.md-5.net/documents'
        #
        # try:
        #    async with aiohttp.ClientSession() as session:
        #        response = await session.post(url, data=content.encode("utf-8"))
        #        response_data = await response.json()
        #        key = response_data['key']
        #        return f"https://paste.md-5.net/{key}"
        # except aiohttp.ClientError as e:
        #    log_tasks.warning(f"Failed to get link: {e}")
        # except asyncio.TimeoutError:
        #    log_tasks.warning("Request to paste.md-5.net timed out.")
        #
        # return "https://paste.md-5.net/"

    @TaskDecorator.task("Fetch All Messages")
    async def fetch_all_messages(self, channel: discord.TextChannel) -> list[discord.Message]:
        return [message async for message in channel.history(limit=None, oldest_first=True)]

    @TaskDecorator.task("Format Embed")
    async def format_embed_content(self, embed: discord.Embed) -> str:
        message_content = ""
        lengths = []
        dictionary = embed.to_dict()
        title = dictionary.get("title", "")
        description = dictionary.get("description", "")
        fields = dictionary.get("fields", [])
        footer = dictionary.get("footer", {}).get("text", "")

        if title:
            lengths.append(len(title))
        if description:
            for line in description.split("\n"):
                lengths.append(len(line))
        for field in fields:
            field_name = field.get("name", "")
            field_value = field.get("value", "")
            lengths.append(len(field_name))
            lengths.append(len(field_value))
        if footer:
            lengths.append(len(footer))

        if lengths:
            max_length = min(max(lengths), 100)
        else:
            return ""

        message_content += "/" + "-" * (int(max_length) + 2) + "\\\n"
        new_line = " "
        if title:
            message_content += f"| {title:{max_length}} |\n"
            message_content += f"| {new_line:{max_length}} |\n"
        if description:
            for line in description.split("\n"):
                substrings = []
                index = 0
                while index < len(line):
                    substrings.append(line[index : index + 100])
                    index += 100
                for sub in substrings:
                    message_content += f"| {sub:{max_length}} |\n"
            message_content += f"| {new_line:{max_length}} |\n"
        for field in fields:
            field_name = field.get("name", "")
            field_value = field.get("value", "")
            message_content += f"| {field_name:{max_length}} |\n{field_value:{max_length}} |\n"
        if footer:
            message_content += f"| {footer:{max_length}} |\n"
        message_content += "\\" + "-" * (int(max_length) + 2) + "/"

        return message_content

    @TaskDecorator.task("Generate Transcript Content")
    async def generate_transcript_content(
        self,
        messages: list[discord.Message],
        opened_string: str,
        ticket_type: str,
        ticket_number: str,
        owner: discord.abc.User,
        owner_id: int,
        reason: str,
        closed_by: discord.Member,
        channel_id: int,
        closed_at_string: str,
        closed_by_id: int,
    ) -> str:
        content: str = (
            f"Minecadia Tickets Bot: {ticket_type}\n- Opened by: {owner} ({owner_id})\n- Opened at: {opened_string}\n- Channel ID: {channel_id}\n- Ticket ID: {ticket_number}\n \n──────────────────────────────────────────────────────\n \n"
        )
        for message in messages:
            try:
                message_content: str = message.content
                for embed in message.embeds:
                    embed_content: str = await self.format_embed_content(embed)
                    message_content += "\n" + embed_content
                created_at = self.convert_to_est(message.created_at.timestamp())
                content += f"[{created_at}]\n{message.author.name} : {message.author.id}"
                if message_content:
                    content += f"\n\t{message_content}"
                content += "\n\n"

            except (DISCORD_API_ERRORS, ValueError, TypeError, AttributeError) as error:
                log_tasks.warning(
                    "Failed logging message %s (%s): %s %s",
                    message.author,
                    message.author.id,
                    message.content,
                    error,
                )

        content += f"──────────────────────────────────────────────────────\n\n- Closure Reason: {reason}\n- Closed By: {closed_by} ({closed_by_id})\n- Closed At: {closed_at_string}"

        return content

    @TaskDecorator.task("Get Ticketlog Embed")
    async def get_ticket_log(
        self,
        reason: str,
        opened_timestamp: int | str,
        ticket_number: str,
        owner_mention: str,
        owner: discord.abc.User,
        link: str,
        ticket_type: str,
        closed_at_timestamp: int,
        closed_by: discord.Member,
    ) -> discord.Embed:
        delta = "N/A"
        if isinstance(opened_timestamp, int):
            seconds = closed_at_timestamp - opened_timestamp
            delta = self.client.app.time_format.seconds_to_format(seconds)

        desc = f"`🎫` **{ticket_type} #{ticket_number}** was closed by {closed_by}\n **Reason:** {reason}\n **Owner:** {owner_mention} / {owner.name}\n **Ticket Duration:** {delta}\n[Ticket Transcript]({link})"
        embed = discord.Embed(color=discord.Color.from_str(ConfigManager.get("EMBED_COLOR")), description=desc)
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text=ConfigManager.get("FOOTER"), icon_url=logo_url)

        return embed

    @TaskDecorator.task("Send Ticketlog", False)
    async def send_ticket_log(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        embed: discord.Embed,
        privated: str,
    ) -> None:
        channel_json_string = (
            "ADMIN_TICKET_LOGS_ID"
            if privated == "Admin"
            else "MANAGEMENT_TICKET_LOGS_ID" if privated == "Management" else "TICKET_LOGS_ID"
        )
        ticket_log_channel_id = ConfigManager.get("CHANNEL_IDS")[channel_json_string]
        ticket_log_channel = guild.get_channel(ticket_log_channel_id)
        if not isinstance(ticket_log_channel, discord.TextChannel):
            log_tasks.warning("Ticket log channel %s is unavailable", ticket_log_channel_id)
            return
        await ticket_log_channel.send(embed=embed, file=discord.File("assets/Logo.png"))

        tasks = [
            overwrite.create_dm()
            for overwrite in channel.overwrites
            if isinstance(overwrite, discord.Member)
            and not overwrite.bot
            and channel.permissions_for(overwrite).view_channel
        ]

        try:
            dm_channels = await asyncio.gather(*tasks)
            send_tasks = [dm.send(embed=embed, file=discord.File("assets/Logo.png")) for dm in dm_channels if dm]
            await asyncio.gather(*send_tasks)
        except (DISCORD_API_ERRORS, OSError, FileNotFoundError) as error:
            log_tasks.warning("Failed to send ticket log: %s", error)

    @TaskDecorator.task("Update Database")
    async def update_database(
        self,
        closed_by: discord.Member,
        reason: str,
        name: str,
        link: str,
        closed_at_timestamp: int,
        channel_id: int,
        closed_by_id: int,
    ) -> None:
        tickets_closed_stat = await is_found(closed_by, "tickets_closed")
        new_ticket_closed_stat: int = tickets_closed_stat + 1

        DatabasePool.execute(
            "UPDATE tickets SET is_active = 0, closed_by_id = %s, closed_at = %s, reason = %s, name = %s, transcript = %s WHERE channel_id = %s",
            (closed_by_id, closed_at_timestamp, reason, name, link, channel_id),
        )
        DatabasePool.execute(
            "UPDATE staff_statistics SET tickets_closed = %s WHERE user_id = %s",
            (new_ticket_closed_stat, closed_by_id),
        )
        from services.active_ticket_cache import active_ticket_cache

        active_ticket_cache.unregister(channel_id)
        analytics.increment_total_stat(str(closed_by_id), "tickets_closed", 1)

    @TaskDecorator.task("Fetch Ticket Info")
    async def fetch_ticket_info(self, channel_id: int) -> tuple:
        bot_account = self.client.user
        if bot_account is None:
            raise RuntimeError("Bot user is not available")
        info = (
            bot_account,
            bot_account.id,
            bot_account.mention,
            0,
            "N/A",
            "0000",
            "Unknown",
            "",
            0,
            "",
        )
        row = DatabasePool.execute(
            "SELECT number, opened_at, privated, type, owner_id FROM tickets WHERE channel_id = %s",
            (channel_id,),
        )
        if row:
            row = row[0]
            opened_timestamp: int = int(float(row["opened_at"]))
            opened_string: str = self.convert_to_est(opened_timestamp)
            ticket_number: str = row["number"]
            privated: str = row["privated"]
            ticket_type: str = row["type"]
            owner: discord.User = await self.client.fetch_user(int(row["owner_id"]))
            owner_id: int = owner.id
            owner_mention: str = owner.mention
            closed_at_timestamp: int = int(time.time())
            closed_at_string: str = self.convert_to_est(closed_at_timestamp)
            info = (
                owner,
                owner_id,
                owner_mention,
                opened_timestamp,
                opened_string,
                ticket_number,
                ticket_type,
                privated,
                closed_at_timestamp,
                closed_at_string,
            )

        return info

    @TaskDecorator.task("Get Ticket Count")
    async def get_ticket_count(self) -> int:
        row = DatabasePool.execute("SELECT COUNT(*) FROM tickets WHERE is_active = 1")
        return int(row[0]["COUNT(*)"])

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: (i.channel_id, i.user.id))
    @app_commands.command(name="close", description="Closes the ticket channel")
    @app_commands.describe(reason="The reason for closing the ticket")
    async def close(self, interaction: discord.Interaction, reason: str) -> None:
        await self.close_command(interaction, reason)

    @TaskDecorator.task("Close Command", False)
    async def close_command(self, interaction: discord.Interaction, reason: str) -> None:
        await interaction.response.defer()
        guild = require_guild(interaction.guild)
        channel = require_text_channel(interaction.channel)
        closed_by = require_member(interaction.user)
        await self.close_ticket_channel(
            guild,
            channel,
            closed_by,
            reason,
        )

    @TaskDecorator.task("Close Ticket Channel", False)
    async def close_ticket_channel(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        closed_by: discord.Member,
        reason: str,
    ) -> None:
        start = time.perf_counter()
        messages = await self.fetch_all_messages(channel)
        channel_id = channel.id
        (
            owner,
            owner_id,
            owner_mention,
            opened_timestamp,
            opened_string,
            ticket_number,
            ticket_type,
            privated,
            closed_at_timestamp,
            closed_at_string,
        ) = await self.fetch_ticket_info(channel_id)

        name = channel.name
        reason = reason.replace("'", " ")
        closed_by_id = closed_by.id
        content = await self.generate_transcript_content(
            messages,
            opened_string,
            ticket_type,
            ticket_number,
            owner,
            owner_id,
            reason,
            closed_by,
            channel_id,
            closed_at_string,
            closed_by_id,
        )

        link = await self.return_link(content)

        embed = await self.get_ticket_log(
            reason,
            opened_timestamp,
            ticket_number,
            owner_mention,
            owner,
            link,
            ticket_type,
            closed_at_timestamp,
            closed_by,
        )
        await self.send_ticket_log(guild, channel, embed, privated)
        await self.update_database(
            closed_by,
            reason,
            name,
            link,
            closed_at_timestamp,
            channel_id,
            closed_by_id,
        )

        await channel.delete()

        ticket_count = await self.get_ticket_count()
        log_commands.info(
            "Closed #%s (%s) in %ss by %s (%s) %s",
            name,
            channel_id,
            str(round((time.perf_counter() - start), 2)),
            closed_by,
            closed_by_id,
            ticket_count,
        )


async def setup(client: TicketsBot) -> None:
    await client.add_cog(Close(client))
