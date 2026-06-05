import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)

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

_bots_env = (
    Path(__file__).resolve().parent.parent.parent.parent / "Websites" / "Bots" / ".env"
)
if _bots_env.exists():
    load_dotenv(_bots_env)


COG_FILES = [file.split(".")[0].title() for file in os.listdir("cogs/") if file.endswith(".py")]


class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix = '.', intents = discord.Intents().all())
        wire_bot(self, bot_name="Tickets", log_commands=log_commands, log_tasks=log_tasks)

    @task("Setup Cogs")
    async def setup_cogs(self):
        await self.load_extension("services.active_ticket_cache")
        for ext in COG_FILES:
            log_tasks.info(f"Loaded cog {ext}.py")
            await self.load_extension("cogs." + ext.lower())

    @task("Register Analytics")
    async def register_analytics(self):
        from core.analytics.register import register_command_tracking

        await register_command_tracking(self)

    @task("Add Views")
    async def add_views(self):
        views: list[discord.ui.View] = [
            TicketsView(), TicketsView2() , TicketLogs()
        ]
        for view in views:
            log_tasks.info(f"Added view {view.__class__.__name__}")
            self.add_view(view)

    @task("Update Presence")
    async def update_presence(self):
        presence = ConfigManager.get("PRESENCE")
        await client.change_presence(activity = discord.Game(name = presence))
        log_tasks.info(f"Updated the bot's presence to {presence}")

    @task("Remove Help")
    async def remove_help(self):
        client.remove_command("help")

    @task("Sync Command Tree")
    async def sync_command_tree(self):
        commands: list[discord.app_commands.AppCommand] = await self.tree.sync()
        command_list: str = ', '.join([command.name for command in commands])
        log_tasks.info(f"Synced {len(commands)} commands {command_list}")

    @task("Start Dashboard HTTP")
    async def setup_dashboard_http(self):
        await start_dashboard_http(self)

    @task("Setup Hook")
    async def setup_hook(self):
        from core.errors.setup import wire_bot_async_setup

        await wire_bot_async_setup(self, bot_name="Tickets", log_tasks=log_tasks)
        self.app = BotApp.from_bot(self)
        await self.setup_cogs()
        await self.register_analytics()
        await self.add_views()
        await self.setup_dashboard_http()

    @task("Logging in")
    async def on_ready(self):
        await self.update_presence()
        await self.remove_help()
        await self.sync_command_tree()
        log_tasks.info(f"Logged in as {client.user} ({client.user.id})")


client = Client()


@task("Tickets Reload Command", True)
async def tickets_reload_command(interaction: discord.Interaction, cog: str):
    if interaction.guild is None:
        return await interaction.response.send_message(content = "Commands cannot be ran in DMs!", ephemeral = True)
    if cog not in COG_FILES:
        await interaction.response.send_message(f"Invalid cog name **{cog}.py**", ephemeral = True)
        return
    await client.reload_extension(f"cogs.{cog.lower()}")
    await interaction.response.send_message(f"Successfully reloaded **{cog}.py**", ephemeral = True)

async def cog_autocomplete(_: discord.Interaction, current: str):
    return [
        app_commands.Choice(name = cog, value = cog)
        for cog in COG_FILES if current.lower() in cog.lower()
    ]

@client.tree.command(name = "tickets-reload", description = "Reloads a Cog Class")
@app_commands.autocomplete(cog = cog_autocomplete)
async def ticketsreload(interaction: discord.Interaction, cog: str):
    await tickets_reload_command(interaction, cog)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("Set DISCORD_TOKEN in .env")

if __name__ == "__main__":
    client.run(TOKEN)