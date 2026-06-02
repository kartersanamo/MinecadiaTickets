from Cogs.sendtickets import TicketsView, TicketsView2, TicketLogs
from Assets.functions import get_data, task, log_tasks
from Assets.dashboard_http import start_dashboard_http
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from dotenv import load_dotenv
import discord
import os

_bots_env = (
    Path(__file__).resolve().parent.parent.parent.parent / "Websites" / "Bots" / ".env"
)
if _bots_env.exists():
    load_dotenv(_bots_env)


COG_FILES = [file.split(".")[0].title() for file in os.listdir("Cogs/") if file.endswith(".py")]


class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix = '.', intents = discord.Intents().all())
        self.data: dict = get_data()
        self.view_list: list[discord.ui.View]

    @task("Setup Cogs")
    async def setup_cogs(self):
        """
        This function is responsible for loading and initializing all the Cogs for the bot.

        Parameters:
        - self (Client): The instance of the Client class. This parameter is automatically passed by Python when the function is called.

        Returns:
        - None. This function is asynchronous and does not return any value.

        The function iterates over the list of Cog files (`COG_FILES`) and loads each Cog using the `load_extension` method of the `self` instance.
        It logs the loading of each Cog using the `info` method of the `log_tasks` logger.
        """
        for ext in COG_FILES:
            log_tasks.info(f"Loaded cog {ext}.py")
            await self.load_extension("Cogs." + ext.lower())

    @task("Add Views")
    async def add_views(self):
        """
        This function initializes and adds the necessary views to the bot.

        Parameters:
        - self (Client): The instance of the Client class. This parameter is automatically passed by Python when the function is called.

        Returns:
        - None. This function is asynchronous and does not return any value.

        The function initializes a list of views (`self.view_list`) by creating instances of `TicketsView`, `TicketsView2`, and `TicketLogs`.
        It then iterates over the `self.view_list` and adds each view to the bot using the `add_view` method.
        Additionally, it logs the addition of each view using the `info` method of the `log_tasks` logger.
        """
        self.view_list = [
            TicketsView(), TicketsView2() , TicketLogs()
        ]
        for view in self.view_list:
            log_tasks.info(f"Added view {view.__class__.__name__}")
            self.add_view(view)

    @task("Update Presence")
    async def update_presence(self):
        """
        This function updates the bot's presence on Discord.

        Parameters:
        - self (Client): The instance of the Client class. This parameter is automatically passed by Python when the function is called.

        Returns:
        - None. This function is asynchronous and does not return any value.

        The function retrieves the bot's presence information from the `data` dictionary attribute of the `self` instance.
        It then uses the `change_presence` method of the `client` object to update the bot's presence to the specified game.
        Finally, it logs the updated presence information using the `info` method of the `log_tasks` logger.
        """
        presence = self.data["PRESENCE"]
        await client.change_presence(activity = discord.Game(name = presence))
        log_tasks.info(f"Updated the bot's presence to {presence}")

    @task("Remove Help")
    async def remove_help(self):
        """
        Removes the default help command from the bot.

        This function is a part of the Client class and is responsible for removing the default "help" command from the bot.
        The "help" command is removed using the `remove_command` method of the `client` object.

        Parameters:
        - self (Client): The instance of the Client class. This parameter is automatically passed by Python when the function is called.

        Returns:
        - None. This function is asynchronous and does not return any value.

        Raises:
        - None. This function does not raise any exceptions.
        """
        client.remove_command("help")

    @task("Sync Command Tree")
    async def sync_command_tree(self):
        """
        This function synchronizes the bot's command tree with the current set of commands.

        Parameters:
        - self: The instance of the Client class.

        Returns:
        - commands (list[discord.app_commands.AppCommand]): A list of the commands that were synchronized.

        This function retrieves the list of commands from the bot's command tree using the `tree.sync()` method.
        It then constructs a string representation of the command names and logs this information using the `log_tasks.info()` method.
        """
        commands: list[discord.app_commands.AppCommand] = await self.tree.sync()
        command_list: str = ', '.join([command.name for command in commands])
        log_tasks.info(f"Synced {len(commands)} commands {command_list}")

    @task("Setup Hook")
    async def setup_hook(self):
        """
        This function is responsible for setting up the bot's cogs and views.
        It first calls the `setup_cogs` method to load all the cogs,
        and then calls the `add_views` method to add the necessary views.

        Parameters:
        - self: The instance of the Client class.

        Returns:
        - None. This function is asynchronous and does not return any value.

        Raises:
        - None. This function does not raise any exceptions.
        """
        await self.setup_cogs()
        import sys
        from pathlib import Path

        _minecadia = Path(__file__).resolve().parent.parent
        if str(_minecadia) not in sys.path:
            sys.path.insert(0, str(_minecadia))
        from _analytics.register import register_command_tracking

        await register_command_tracking(self)
        await self.add_views()
        await start_dashboard_http(self)
    
    @task("Logging in")
    async def on_ready(self):
        """
        This function is called when the bot is ready and logged in. It updates the bot's presence, removes the default help command, syncs the command tree, and logs the login information.

        Parameters:
        - self: The instance of the Client class.

        Returns:
        - None. This function is asynchronous and does not return any value.

        Raises:
        - None. This function does not raise any exceptions.
        """
        await self.update_presence()
        await self.remove_help()
        await self.sync_command_tree()
        log_tasks.info(f"Logged in as {client.user} ({client.user.id})")


client = Client()

@task("Tickets Reload Command", True)
async def tickets_reload_command(interaction: discord.Interaction, cog: str):
    """
    This function is responsible for reloading a specific Cog class.

    Parameters:
    - interaction (discord.Interaction): The Discord interaction object that triggered the command.
    - cog (str): The name of the Cog class to be reloaded.

    Returns:
    - None. This function is asynchronous and does not return any value.

    Raises:
    - discord.app_commands.AppCommandError: If there is an error while reloading the Cog class.
    """
    if interaction.guild is None:
        return await interaction.response.send_message(content = "Commands cannot be ran in DMs!", ephemeral = True)
    if cog not in COG_FILES:
        await interaction.response.send_message(f"Invalid cog name **{cog}.py**", ephemeral = True)
        return
    await client.reload_extension(f"Cogs.{cog.lower()}")
    await interaction.response.send_message(f"Successfully reloaded **{cog}.py**", ephemeral = True)

async def cog_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name = cog, value = cog)
        for cog in COG_FILES if current.lower() in cog.lower()
    ]

@client.tree.command(name = "tickets-reload", description = "Reloads a Cog Class")
@app_commands.autocomplete(cog = cog_autocomplete)
async def ticketsreload(interaction: discord.Interaction, cog: str):
    """
    This function is responsible for triggering the reload of a specific Cog class based on the user's interaction.

    Parameters:
    - interaction (discord.Interaction): The Discord interaction object that triggered the command.
    - cog (str): The name of the Cog class to be reloaded. The input is restricted to a specific set of strings as determined by the 'cog_autocomplete' function.

    Returns:
    - None. This function is asynchronous and does not return any value. It triggers the reload of the specified Cog class.

    Raises:
    - discord.app_commands.AppCommandError: If there is an error while reloading the Cog class.
    """
    await tickets_reload_command(interaction, cog)

@ticketsreload.error
async def ticketsreload_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


if __name__ == "__main__":
    client.run(client.data['TOKEN'])