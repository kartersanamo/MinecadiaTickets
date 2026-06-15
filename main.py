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

from core.analytics.register import register_command_tracking
from core.guild_command_sync import sync_guild_commands
from assets.dashboard_http import start_dashboard_http
from ui.views.tickets_view2_view import TicketsView2
from core.errors.setup import wire_bot_async_setup
from core.loggers import log_commands, log_tasks
from ui.views.ticket_logs_view import TicketLogs
from ui.views.tickets_view import TicketsView
from core.errors.setup import wire_bot
from core.config import ConfigManager
from core.decorators import task
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
        wire_bot(bot = self, bot_name = "Tickets", log_commands = log_commands, log_tasks = log_tasks)
        log_tasks.info(msg = "Initialized the bot client")

    @task(action_name = "Setup Cogs")
    async def _setup_cogs(self) -> None:
        """Loads all cogs in the cogs directory and the active ticket cache service."""
        try:
            await self.load_extension(name = "services.active_ticket_cache")
            for ext in COG_FILES:
                await self.load_extension(name = "cogs." + ext.lower())
        except (commands.ExtensionNotLoaded, commands.ExtensionNotFound, commands.NoEntryPointError, commands.ExtensionFailed) as exc:
            log_commands.error(msg = f"Failed to load extension {exc}")    
        log_tasks.info(msg = f"Loaded {len(COG_FILES)} cogs {', '.join(ext + '.py' for ext in COG_FILES)}")

    @task(action_name = "Register Analytics")
    async def _register_analytics(self) -> None:
        """Registers command analytics tracking for the bot."""
        await register_command_tracking(bot = self)
        log_tasks.info(msg = f"Registered command analytics tracking")

    @task(action_name = "Add Views")
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

    @task(action_name = "Update Presence")
    async def _update_presence(self) -> None:
        """Updates the bot's presence based on the configuration."""
        presence: str = ConfigManager.get(key = "PRESENCE")
        await self.change_presence(activity = discord.Game(name = presence))
        log_tasks.info(msg = f"Updated the bot's presence to {presence}")

    @task(action_name = "Remove Help")
    async def _remove_help(self) -> None:
        """Removes the default help command as we don't use this."""
        self.remove_command("help")
        log_tasks.info(msg = "Removed the default help command")

    @task(action_name = "Sync Command Tree")
    async def _sync_command_tree(self) -> None:
        """Syncs the bot's command tree with the guild specified in the configuration."""
        await sync_guild_commands(
            bot = self,
            config_guild_id=ConfigManager.get(key = "GUILD_ID"),
            log = log_tasks,
            also_sync_global = False,
            clear_global_after_guild = True
        )

    @task(action_name = "Start Dashboard HTTP")
    async def _setup_dashboard_http(self) -> None:
        """Starts the dashboard HTTP server in the background."""
        await start_dashboard_http(client = self)
        log_tasks.info(msg = "Started the dashboard HTTP server")

    @task(action_name = "Setup Hook")
    async def setup_hook(self) -> None:
        """Overrides the default setup_hook to perform asynchronous setup tasks before the bot is ready."""
        await wire_bot_async_setup(bot = self, bot_name = "Tickets", log_tasks = log_tasks)
        self.app: BotApp = BotApp.from_bot(bot = self)
        await self._setup_cogs()
        await self._register_analytics()
        await self._add_views()
        await self._setup_dashboard_http()
        log_tasks.info(msg = "Completed bot setup hook")

    @task(action_name = "Logging in")
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


@task(action_name = "Tickets Reload Command", log = True)
async def tickets_reload_command(interaction: discord.Interaction, cog: str) -> None:
    """
    Handles the /tickets-reload command to reload a specified cog.
    Args:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        cog (str): The name of the cog to reload, provided by the user.
    Examples:
        /tickets-reload cog:managetickets
        >>> tickets_reload_command(interaction, "managetickets")
    """
    if cog not in COG_FILES:
        await interaction.response.send_message(content = f"Invalid cog name **{cog}.py**", ephemeral = True)
        log_commands.warning(msg = f"User {interaction.user} ({interaction.user.id}) attempted to reload invalid cog {cog}.py")
        return
    try:
        await client.reload_extension(name = f"cogs.{cog.lower()}")
        log_commands.info(msg = f"User {interaction.user} ({interaction.user.id}) reloaded cog {cog}.py")
        await interaction.response.send_message(content = f"Successfully reloaded **{cog}.py**", ephemeral = True)
    except (commands.ExtensionNotLoaded, commands.ExtensionNotFound, commands.NoEntryPointError, commands.ExtensionFailed) as exc:
        log_commands.error(msg = f"{interaction.user} ({interaction.user.id}) failed to reload extension {cog}: {exc}")
        await interaction.response.send_message(content = f"Failed to reload **{cog}.py** due to an exception", ephemeral = True)

@task(action_name = "Cog Autocomplete")
async def cog_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Provides autocomplete suggestions for the cog parameter in the /tickets-reload command.
    Args:
        _ (discord.Interaction): The interaction object representing the autocomplete request (not used in this function).
        current (str): The current input from the user for the cog parameter, used to filter the suggestions.
    Returns:
        A list of app_commands.Choice objects representing the autocomplete suggestions for the cog parameter. Each choice has a name and value corresponding to a cog file that matches the current input.
    Examples:
        /tickets-reload cog:ti
        >>> cog_autocomplete(interaction, "ti")
        ["managetickets.py", "ticketlogs.py", "sendtickets.py", "activetickets.py", "ticketcount.py"]
    """
    return [
        app_commands.Choice(name = cog, value = cog)
        for cog in COG_FILES if current.lower() in cog.lower()
    ]

@app_commands.guild_only()
@app_commands.describe(cog = "The cog to reload")
@app_commands.autocomplete(cog = cog_autocomplete)
@client.tree.command(name = "tickets-reload", description = "Reloads a Cog Class")
async def ticketsreload(interaction: discord.Interaction, cog: str) -> None:
    """Handles the /tickets-reload command to reload a specified cog. 
    
    This command is restricted to guilds and includes autocomplete for the cog parameter.
    It calls the tickets_reload_command function to perform the actual reloading of the cog and sends an appropriate response based on the outcome.
    
    Args:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        cog (str): The name of the cog to reload, provided by the user.
    Examples:
        /tickets-reload cog:managetickets
        >>> ticketsreload(interaction, "managetickets")
    """
    await tickets_reload_command(interaction = interaction, cog = cog)

TOKEN: str | None = os.getenv(key = "DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("Set DISCORD_TOKEN in .env")

if __name__ == "__main__":
    client.run(token = TOKEN)