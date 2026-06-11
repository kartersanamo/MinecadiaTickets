"""
main.py

This file is the main entry point for the MinecadiaTickets bot.
It initializes the bot, loads cogs, and starts the bot.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""

import os
from pathlib import Path

os.chdir(path = Path(__file__).resolve().parent)

from ui.views.ticket_logs_view import TicketLogs
from ui.views.tickets_view import TicketsView
from ui.views.tickets_view2_view import TicketsView2
from assets.dashboard_http import start_dashboard_http

from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import discord
from core.app import BotApp
from core.config import ConfigManager
from core.decorators import task
from core.loggers import log_commands, log_tasks
from core.errors.setup import wire_bot

_bots_env: Path = (
    Path(__file__).resolve().parent.parent.parent.parent / "Websites" / "Bots" / ".env"
)
if _bots_env.exists():
    load_dotenv(dotenv_path = _bots_env)


COG_FILES = [file.split(sep = ".")[0].title() for file in os.listdir(path = "cogs/") if file.endswith(".py")]
    

class Client(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix = '.', intents = discord.Intents().all())
        wire_bot(bot = self, bot_name = "Tickets", log_commands = log_commands, log_tasks = log_tasks)

    @task(action_name = "Setup Cogs", log = False)
    async def setup_cogs(self) -> None:
        await self.load_extension(name = "services.active_ticket_cache")
        for ext in COG_FILES:
            log_tasks.info(msg = f"Loaded cog {ext}.py")
            await self.load_extension(name = "cogs." + ext.lower())

    @task(action_name = "Register Analytics", log = False)
    async def register_analytics(self) -> None:
        from core.analytics.register import register_command_tracking
        await register_command_tracking(bot = self)

    @task(action_name = "Add Views", log = False)
    async def add_views(self) -> None:
        views: list[discord.ui.View] = [
            TicketsView(), TicketsView2() , TicketLogs()
        ]
        for view in views:
            log_tasks.info(msg = f"Added view {view.__class__.__name__}")
            self.add_view(view = view)

    @task(action_name = "Update Presence", log = False)
    async def update_presence(self) -> None:
        presence = ConfigManager.get(key = "PRESENCE")
        await self.change_presence(activity = discord.Game(name = presence))
        log_tasks.info(msg = f"Updated the bot's presence to {presence}")

    @task(action_name = "Remove Help", log = False)
    async def remove_help(self) -> None:
        self.remove_command("help")

    @task(action_name = "Sync Command Tree", log = False)
    async def sync_command_tree(self) -> None:
        from core.guild_command_sync import sync_guild_commands

        await sync_guild_commands(
            bot = self,
            config_guild_id=ConfigManager.get(key = "GUILD_ID"),
            log = log_tasks,
        )

    @task(action_name = "Start Dashboard HTTP", log = False)
    async def setup_dashboard_http(self) -> None:
        await start_dashboard_http(client = self)

    @task(action_name = "Setup Hook", log = False)
    async def setup_hook(self) -> None:
        from core.errors.setup import wire_bot_async_setup

        await wire_bot_async_setup(bot = self, bot_name = "Tickets", log_tasks = log_tasks)
        self.app = BotApp.from_bot(bot = self)
        await self.setup_cogs()
        await self.register_analytics()
        await self.add_views()
        await self.setup_dashboard_http()

    @task(action_name = "Logging in", log = False)
    async def on_ready(self) -> None:
        await self.update_presence()
        await self.remove_help()
        await self.sync_command_tree()
        if not self.user:
            log_tasks.error(msg = "Failed to get user information on login!")
            return
        log_tasks.info(msg = f"Logged in as {self.user} ({self.user.id})")


client = Client()


@task(action_name = "Tickets Reload Command", log = True)
async def tickets_reload_command(interaction: discord.Interaction, cog: str) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(content = "Commands cannot be ran in DMs!", ephemeral = True)
        return
    if cog not in COG_FILES:
        await interaction.response.send_message(content = f"Invalid cog name **{cog}.py**", ephemeral = True)
        return
    await client.reload_extension(f"cogs.{cog.lower()}")
    await interaction.response.send_message(content = f"Successfully reloaded **{cog}.py**", ephemeral = True)

async def cog_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name = cog, value = cog)
        for cog in COG_FILES if current.lower() in cog.lower()
    ]

@client.tree.command(name = "tickets-reload", description = "Reloads a Cog Class")
@app_commands.autocomplete(cog = cog_autocomplete)
async def ticketsreload(interaction: discord.Interaction, cog: str) -> None:
    await tickets_reload_command(interaction = interaction, cog = cog)

TOKEN = os.getenv(key = "DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("Set DISCORD_TOKEN in .env")

if __name__ == "__main__":
    client.run(token = TOKEN)