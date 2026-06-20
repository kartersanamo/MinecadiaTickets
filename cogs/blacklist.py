"""
blacklist.py

This file is the cog for the blacklist command.
It is used to blacklist a user from opening tickets and unblacklist them after a certain time.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""
from discord.ext import commands, tasks
from discord import app_commands
from discord import Webhook
from typing import Literal, Optional

from core.bot_client import TicketsBot
import datetime
import aiohttp
import discord
import time
from core.config import ConfigManager
from core.database import DatabasePool
from core.decorators import TaskDecorator
from core.loggers import log_commands, log_tasks

class Blacklist(commands.Cog):
    def __init__(self, client: TicketsBot) -> None:
        self.client: TicketsBot = client
        self.check_blacklists.start()
  
    async def cog_unload(self) -> None:
        self.check_blacklists.stop()

    @tasks.loop(minutes = 10)
    async def check_blacklists(self) -> None:
        current_time: int = int(time.time())
        rows: list = DatabasePool.execute(
            "SELECT user_id FROM blacklists WHERE unblacklist_at < %s",
            (current_time,),
        )
        if rows:
            user_ids: list = [str(row['user_id']) for row in rows]
            log_tasks.info(f"Removing ticket blacklists {user_ids}")
            await self.remove_blacklists(user_ids)
        
    @TaskDecorator.task("Remove Blacklists", False)
    async def remove_blacklists(self, user_ids: list[str]) -> None:
        if not user_ids:
            return
        placeholders = ", ".join(["%s"] * len(user_ids))
        DatabasePool.execute(f"DELETE FROM blacklists WHERE user_id IN ({placeholders})", tuple(user_ids))

    @TaskDecorator.task("Get Unix", False)
    async def get_unix(self, length: str) -> int:
        current_unix = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        length_in_secs = int(length.split("d")[0]) * 86400
        return current_unix + length_in_secs

    @TaskDecorator.task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        existing_row = DatabasePool.execute("SELECT * FROM blacklists WHERE user_id = %s", (user.id,))
        if existing_row:
            await self.remove_blacklists([str(user.id)])
            await self.send_embed(interaction, user, "unblacklisted")
            log_commands.info(f"{user} ({user.id}) has been unblacklisted from creating tickets by a staff member")
            return True
        return False

    @TaskDecorator.task("Blacklist User", False)
    async def blacklist_user(self, interaction: discord.Interaction, user: discord.Member, length: str, reason: Optional[str] = None) -> None:
        unix = await self.get_unix(length)
        DatabasePool.execute(
            "INSERT INTO blacklists (user_id, reason, staff_id, unblacklist_at, created_at) VALUES (%s, %s, %s, %s, %s)",
            (user.id, reason or "N/A", interaction.user.id, unix, int(__import__("time").time())),
        )
        log_commands.info(f"Ticket blacklisted {user} ({user.id}) for {length}")

    @TaskDecorator.task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, user: discord.Member, blacklisted: str) -> None:
        embed = discord.Embed(
            description = f"{interaction.user.mention} has **{blacklisted}** {user.mention} from opening tickets",
            color = discord.Color.from_str(ConfigManager.get('EMBED_COLOR')))
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text = ConfigManager.get("FOOTER"), icon_url = logo_url)
        await interaction.response.send_message(embed = embed, file = discord.File("assets/Logo.png"))

    @TaskDecorator.task("Send Webhook", False)
    async def send_webhook(self, interaction: discord.Interaction, user: discord.Member, length: str, reason: Optional[str] = None) -> None:
        unix: int = await self.get_unix(length)
        embed = discord.Embed(
            title = "Ticket Blacklist", 
            color = discord.Color.from_str(ConfigManager.get("EMBED_COLOR")), 
            description = f"`IGN` {user.display_name}\n`Discord` {user}\n`Reason` {reason or 'N/A'}\n`Expires` <t:{unix}:R>", 
            timestamp = datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_author(name = interaction.user.display_name, icon_url = interaction.user.avatar)

        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(ConfigManager.get("TICKET_BLACKLIST_WEBHOOK"), session = session)
            await webhook.send(embed = embed, username = "Ticket Blacklists")

    @app_commands.guild_only()
    @app_commands.command(name = "blacklist", description = "Blacklists a member from opening tickets")
    @app_commands.describe(user = "The user to blacklist from opening tickets", length = "When this user should be unblacklisted from tickets", reason = "The reason for blacklisting the user")
    async def blacklist(self, interaction: discord.Interaction, user: discord.Member, length: Literal["1d", "2d", "3d", "4d", "5d", "6d", "7d", "10d", "14d", "28d", "30d"], reason: Optional[str] = None) -> None:
        await self.blacklist_command(interaction, user, length, reason)
    
    @TaskDecorator.task("Blacklist Command", True)
    async def blacklist_command(self, interaction: discord.Interaction, user: discord.Member, length: str, reason: Optional[str] = None) -> None:
        blacklisted: bool = await self.check_blacklisted(interaction, user)
        if not blacklisted:
            await self.blacklist_user(interaction, user, length, reason)
            await self.send_embed(interaction, user, "blacklisted")
            await self.send_webhook(interaction, user, length, reason)



async def setup(client: TicketsBot) -> None:
  await client.add_cog(Blacklist(client))