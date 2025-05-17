from Assets.functions import log_commands, get_data, execute, task
from discord.ext import commands, tasks
import discord


class Logs(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.data: dict = get_data()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """
        This function is an event listener that is triggered when the Logs Cog is ready.
        It starts the `update_ticket_vc_count_loop` task.

        Parameters:
        self (Logs): The instance of the Logs class that called this method.

        Returns:
        None. This function is an asynchronous method and does not return a value.
        It starts the `update_ticket_vc_count_loop` task.
        """
        # await self.update_ticket_vc_count_loop.start() Turned off due to rate limits

    @task("Get Ticket Count")
    async def get_ticket_count(self) -> int:
        """
        This function retrieves the count of active tickets from the database.

        Parameters:
        None

        Returns:
        int: The count of active tickets.
        """
        row = execute("SELECT COUNT(*) FROM tickets WHERE active = 'True'")
        return int(row[0]['COUNT(*)'])

    @task("Update Ticket VC Count")
    async def update_ticket_vc_count(self) -> None:
        """
        This function updates the name of a voice channel to reflect the current count of active tickets.

        Parameters:
        self (Logs): The instance of the Logs class that called this method.

        Returns:
        None. This function is an asynchronous method and does not return a value.
        """
        new_ticket_count: int = await self.get_ticket_count()
        guild = self.client.get_guild(self.data['GUILD_ID'])
        channel = guild.get_channel(self.data['CHANNEL_IDS']['TICKET_COUNT_VOICE_CHANNEL_ID'])
        await channel.edit(name = f"Tickets: {new_ticket_count}")

    @tasks.loop(minutes = 5)
    async def update_ticket_vc_count_loop(self):
        """
        This function is a loop that updates the name of a voice channel to reflect the current count of active tickets every 5 minutes.

        Parameters:
        self (Logs): The instance of the Logs class that called this method.

        Returns:
        None. This function is an asynchronous method and does not return a value. It updates the voice channel name using the `update_ticket_vc_count` method.
        """
        await self.update_ticket_vc_count()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        This function is a Discord interaction event listener that logs command usage.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered the event.

        Returns:
        None. This function is an event listener and does not return a value.
        """
        if interaction.type == discord.InteractionType.application_command:
            name = f"/{interaction.command.name}"
            try:
                for option in interaction.data['options']:
                    name += f" {option['name']}:'{option['value']}'"
            except KeyError:
                pass
            log_commands.info(f"{interaction.user} ({interaction.user.id}) ran {name} in #{interaction.channel} ({interaction.channel.id}) {not interaction.command_failed}")


async def setup(client:commands.Bot) -> None:
    await client.add_cog(Logs(client))