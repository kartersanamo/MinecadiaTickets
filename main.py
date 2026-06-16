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

from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import discord

from core.analytics.register import CommandTrackingRegistrar
from core.guild_command_sync import GuildCommandSync
from assets.dashboard_http import DashboardHttp
from ui.views.tickets_view2_view import TicketsView2
from core.errors.setup import ErrorSetup
from core.loggers import log_commands, log_tasks
from ui.views.ticket_logs_view import TicketLogs
from ui.views.tickets_view import TicketsView
from core.config import ConfigManager
from core.decorators import TaskDecorator
from core.app import BotApp

_bots_env: Path = (
    Path(__file__).resolve().parent.parent.parent.parent / "Websites" / "Bots" / ".env"
)
if _bots_env.exists():
    load_dotenv(dotenv_path = _bots_env)


COG_FILES: list[str] = [file.split(sep = ".")[0].title() for file in os.listdir(path = "cogs/") if file.endswith(".py")]


class Client(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix = '.', intents = discord.Intents().all())
        ErrorSetup.wire_bot(bot = self, bot_name = "Tickets", log_commands = log_commands, log_tasks = log_tasks)
        log_tasks.info(msg = "Initialized the bot client")

    @TaskDecorator.task(action_name = "Setup Cogs")
    async def _setup_cogs(self) -> None:
        """Loads all cogs in the cogs directory and the active ticket cache service."""
        loaded: list[str] = []
        for ext in ("services.active_ticket_cache", *(f"cogs.{name.lower()}" for name in COG_FILES)):
            try:
                await self.load_extension(name=ext)
                loaded.append(ext)
            except (commands.ExtensionNotLoaded, commands.ExtensionNotFound, commands.NoEntryPointError, commands.ExtensionFailed) as exc:
                log_commands.error(msg=f"Failed to load extension {ext}: {exc}")
        log_tasks.info(msg=f"Loaded {len(loaded)} extensions: {', '.join(loaded)}")

    @TaskDecorator.task(action_name = "Register Analytics")
    async def _register_analytics(self) -> None:
        """Registers command analytics tracking for the bot."""
        await CommandTrackingRegistrar.register_command_tracking(bot = self)
        log_tasks.info(msg = f"Registered command analytics tracking")

    @TaskDecorator.task(action_name = "Add Views")
    async def _add_views(self) -> None:
        """Adds all views to the bot."""
        views: list[discord.ui.View] = [
            TicketsView(), TicketsView2() , TicketLogs()
        ]
        for view in views:
            try:
                self.add_view(view = view)
            except ValueError as exc:
                log_tasks.error(msg = f"Failed to add view {view.__class__.__name__}: {exc}")
        log_tasks.info(msg = f"Added views {', '.join(view.__class__.__name__ for view in views)}")

    @TaskDecorator.task(action_name = "Update Presence")
    async def _update_presence(self) -> None:
        """Updates the bot's presence based on the configuration."""
        presence: str = ConfigManager.get(key = "PRESENCE")
        await self.change_presence(activity = discord.Game(name = presence))
        log_tasks.info(msg = f"Updated the bot's presence to {presence}")

    @TaskDecorator.task(action_name = "Remove Help")
    async def _remove_help(self) -> None:
        """Removes the default help command as we don't use this."""
        self.remove_command("help")
        log_tasks.info(msg = "Removed the default help command")

    @TaskDecorator.task(action_name = "Sync Command Tree")
    async def _sync_command_tree(self) -> None:
        """Syncs the bot's command tree with the guild specified in the configuration."""
        await GuildCommandSync.sync_guild_commands(
            bot = self,
            config_guild_id=ConfigManager.get(key = "GUILD_ID"),
            log = log_tasks,
            also_sync_global = False,
            clear_global_after_guild = True
        )

    @TaskDecorator.task(action_name = "Start Dashboard HTTP")
    async def _setup_dashboard_http(self) -> None:
        """Starts the dashboard HTTP server in the background."""
        await DashboardHttp.start(client = self)
        log_tasks.info(msg = "Started the dashboard HTTP server")

    def _register_reload_command(self) -> None:
        bot = self

        @app_commands.guild_only()
        @app_commands.describe(cog = "The cog to reload")
        @app_commands.autocomplete(cog = bot.cog_autocomplete)
        @bot.tree.command(name = "tickets-reload", description = "Reloads a Cog Class")
        async def tickets_reload_slash(interaction: discord.Interaction, cog: str) -> None:
            await bot.tickets_reload_command(interaction, cog)

    @TaskDecorator.task(action_name = "Tickets Reload Command", log = True)
    async def tickets_reload_command(self, interaction: discord.Interaction, cog: str) -> None:
        if cog not in COG_FILES:
            await interaction.response.send_message(content = f"Invalid cog name **{cog}.py**", ephemeral = True)
            log_commands.warning(msg = f"User {interaction.user} ({interaction.user.id}) attempted to reload invalid cog {cog}.py")
            return
        try:
            await self.reload_extension(name = f"cogs.{cog.lower()}")
            log_commands.info(msg = f"User {interaction.user} ({interaction.user.id}) reloaded cog {cog}.py")
            await interaction.response.send_message(content = f"Successfully reloaded **{cog}.py**", ephemeral = True)
        except (commands.ExtensionNotLoaded, commands.ExtensionNotFound, commands.NoEntryPointError, commands.ExtensionFailed) as exc:
            log_commands.error(msg = f"{interaction.user} ({interaction.user.id}) failed to reload extension {cog}: {exc}")
            await interaction.response.send_message(content = f"Failed to reload **{cog}.py** due to an exception", ephemeral = True)

    @TaskDecorator.task(action_name = "Cog Autocomplete")
    async def cog_autocomplete(self, _: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name = cog, value = cog)
            for cog in COG_FILES if current.lower() in cog.lower()
        ]


    @TaskDecorator.task(action_name = "Setup Hook")
    async def setup_hook(self) -> None:
        """Overrides the default setup_hook to perform asynchronous setup tasks before the bot is ready."""
        await ErrorSetup.wire_bot_async_setup(bot = self, bot_name = "Tickets", log_tasks = log_tasks)
        self.app: BotApp = BotApp.from_bot(bot = self)
        self._register_reload_command()
        await self._setup_cogs()
        await self._register_analytics()
        await self._add_views()
        await self._setup_dashboard_http()
        log_tasks.info(msg = "Completed bot setup hook")

    @TaskDecorator.task(action_name = "Logging in")
    async def on_ready(self) -> None:
        """Overrides the default on_ready event to perform tasks when the bot is ready."""
        await self._update_presence()
        await self._remove_help()
        await self._sync_command_tree()
        if not self.user:
            log_tasks.error(msg = "Failed to get user information on login!")
            return
        log_tasks.info(msg = f"Logged in as {self.user} ({self.user.id})")


client = Client()

TOKEN: str | None = os.getenv(key = "DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("Set DISCORD_TOKEN in .env")

if __name__ == "__main__":
    client.run(token = TOKEN)
