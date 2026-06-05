from discord.ext import commands, tasks
import discord
from core.config import ConfigManager
from core.database import aexecute
from core.decorators import task
from core.loggers import log_commands


class Logs(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
    @commands.Cog.listener()
    async def on_ready(self):
        # await self.update_ticket_vc_count_loop.start() Turned off due to rate limits
        pass

    @task("Get Ticket Count")
    async def get_ticket_count(self) -> int:
        row = await aexecute("SELECT COUNT(*) AS n FROM tickets WHERE active = %s", ("True",))
        if not row:
            return 0
        return int(row[0].get("n") or row[0].get("COUNT(*)") or 0)

    @task("Update Ticket VC Count")
    async def update_ticket_vc_count(self) -> None:
        new_ticket_count: int = await self.get_ticket_count()
        guild = self.client.get_guild(ConfigManager.get('GUILD_ID'))
        channel = guild.get_channel(ConfigManager.get('CHANNEL_IDS')['TICKET_COUNT_VOICE_CHANNEL_ID'])
        await channel.edit(name = f"Tickets: {new_ticket_count}")

    @tasks.loop(minutes = 5)
    async def update_ticket_vc_count_loop(self):
        await self.update_ticket_vc_count()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.application_command:
            name = f"/{interaction.command.name}"
            try:
                for option in interaction.data.get('options'):
                    name += f" {option['name']}:'{option['value']}'"
            except KeyError:
                pass
            log_commands.info(f"{interaction.user} ({interaction.user.id}) ran {name} in #{interaction.channel} ({interaction.channel.id}) {not interaction.command_failed}")


async def setup(client:commands.Bot) -> None:
    await client.add_cog(Logs(client))