from Assets.functions import get_data, execute, log_commands, task, log_tasks
from discord.ext import commands, tasks
from discord import app_commands
from discord import Webhook
from typing import Literal
import datetime
import aiohttp
import discord
import time

class Blacklist(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()
        self.check_blacklists.start()
  
    def cog_unload(self) -> None:
        self.check_blacklists.stop()

    @tasks.loop(minutes = 10)
    async def check_blacklists(self) -> None:
        """
        This function is a task that runs every 10 minutes. It checks the database for users who have a blacklist expiration time
        less than the current time. If such users are found, it logs the action and removes their blacklists.

        Parameters:
        None

        Returns:
        None
        """
        current_time: int = int(time.time())
        rows: list = execute(f"SELECT userID FROM blacklists WHERE whenToUnbl < '{current_time}'")
        if rows:
            user_ids: list = [str(row['userID']) for row in rows]
            log_tasks.info(f"Removing ticket blacklists {user_ids}")
            user_ids_str: str = ', '.join(user_ids)
            await self.remove_blacklists(user_ids_str)
        
    @task("Remove Blacklists", False)
    async def remove_blacklists(self, user_ids: str) -> None:
        """
        This function removes blacklisted users from the database.

        Parameters:
        user_ids (str): A string containing the user IDs of the blacklisted users, separated by commas.

        Returns:
        None: This function does not return any value. It only executes a database query to remove the blacklisted users.
        """
        execute(f"DELETE FROM blacklists WHERE userID IN ({user_ids})")

    @task("Get Unix", False)
    async def get_unix(self, length: str) -> int:
        """
        This function calculates the Unix timestamp for a given duration in days.

        Parameters:
        length (str): The duration in days for which the Unix timestamp needs to be calculated. 
                        The input should be a string in the format "Xd", where X is the number of days.

        Returns:
        int: The Unix timestamp corresponding to the given duration in days.
        """
        current_unix = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        length_in_secs = int(length.split("d")[0]) * 86400
        return current_unix + length_in_secs

    @task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        """
        This function checks if a user is currently blacklisted from creating tickets.
        If the user is found in the blacklist, it removes the user from the blacklist, sends an embed and logs the action.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        user (discord.Member): The user to check for blacklisting.

        Returns:
        bool: True if the user is found in the blacklist and has been unblacklisted, False otherwise.
        """
        existing_row = execute(f"SELECT * FROM blacklists WHERE userID = {user.id}")
        if existing_row:
            await self.remove_blacklists(str(user.id))
            await self.send_embed(interaction, user, "unblacklisted")
            log_commands.info(f"{user} ({user.id}) has been unblacklisted from creating tickets by a staff member")
            return True
        return False

    @task("Blacklist User", False)
    async def blacklist_user(self, interaction: discord.Interaction, user: discord.Member, length: str, reason: str) -> None:
        """
        This function adds a user to the ticket blacklist. It calculates the expiration time based on the provided length,
        inserts the user's information into the database, and logs the action.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        user (discord.Member): The user to be blacklisted.
        length (str): The duration for which the user should be blacklisted.
        reason (str): The reason for blacklisting the user. If not provided, it defaults to 'N/A'.

        Returns:
        None
        """
        unix = await self.get_unix(length)
        execute(f"INSERT INTO blacklists(userID, reason, staffID, whenToUnbl, created_at) VALUES ('{user.id}', '{reason or 'N/A'}', '{interaction.user.id}', '{unix}', '{int(__import__('time').time())}')")
        log_commands.info(f"Ticket blacklisted {user} ({user.id}) for {length}")

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, user: discord.Member, blacklisted: str) -> None:
        """
        This function sends an embed message to the interaction response, containing information about a ticket blacklist.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        user (discord.Member): The user who is being blacklisted or unblacklisted.
        blacklisted (str): A string indicating whether the user is being blacklisted or unblacklisted. It should be either "blacklisted" or "unblacklisted".

        Returns:
        None
        """
        embed = discord.Embed(
            description = f"{interaction.user.mention} has **{blacklisted}** {user.mention} from opening tickets",
            color = discord.Color.from_str(self.data['EMBED_COLOR']))
        from Assets.functions import get_embed_logo_url
        logo_url = get_embed_logo_url(self.data["LOGO"])
        embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
        await interaction.response.send_message(embed = embed, file = discord.File("Assets/Logo.png"))

    @task("Send Webhook", False)
    async def send_webhook(self, interaction: discord.Interaction, user: discord.Member, length: str, reason: str) -> None:
        """
        This function sends a webhook notification containing information about a ticket blacklist.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        user (discord.Member): The user who is being blacklisted.
        length (str): The duration for which the user is blacklisted.
        reason (str): The reason for blacklisting the user.

        Returns:
        None
        """
        unix: int = await self.get_unix(length)
        embed = discord.Embed(
            title = "Ticket Blacklist", 
            color = discord.Color.from_str(self.data["EMBED_COLOR"]), 
            description = f"`IGN` {user.display_name}\n`Discord` {user}\n`Reason` {reason or 'N/A'}\n`Expires` <t:{unix}:R>", 
            timestamp = datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_author(name = interaction.user.display_name, icon_url = interaction.user.avatar)

        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(self.data["TICKET_BLACKLIST_WEBHOOK"], session = session)
            await webhook.send(embed = embed, username = "Ticket Blacklists")

    @app_commands.guild_only()
    @app_commands.command(name = "blacklist", description = "Blacklists a member from opening tickets")
    @app_commands.describe(user = "The user to blacklist from opening tickets", length = "When this user should be unblacklisted from tickets", reason = "The reason for blacklisting the user")
    async def blacklist(self, interaction: discord.Interaction, user: discord.Member, length: Literal["1d", "2d", "3d", "4d", "5d", "6d", "7d", "10d", "14d", "28d", "30d"], reason: str = None) -> None:
        """
        This function is responsible for handling the blacklist command in a Discord bot. It checks if a user is already blacklisted,
        if not, it adds the user to the blacklist, sends an embed and a webhook notification.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        user (discord.Member): The user to be blacklisted. This user must be a member of the guild where the command is invoked.
        length (str): The duration for which the user should be blacklisted. The length must be one of the following: "1d", "2d", "3d", "4d", "5d", "6d", "7d", "10d", "14d", "28d", "30d".
        reason (str, optional): The reason for blacklisting the user. Defaults to None.

        Returns:
        None
        """
        await self.blacklist_command(interaction, user, length, reason)
    
    @task("Blacklist Command", True)
    async def blacklist_command(self, interaction: discord.Interaction, user: discord.Member, length: str, reason: str = None) -> None:
        """
        This function is responsible for handling the blacklist command. It checks if a user is already blacklisted,
        if not, it adds the user to the blacklist, sends an embed and a webhook notification.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        user (discord.Member): The user to be blacklisted.
        length (str): The duration for which the user should be blacklisted.
        reason (str, optional): The reason for blacklisting the user. Defaults to None.

        Returns:
        None
        """
        blacklisted: bool = await self.check_blacklisted(interaction, user)
        if not blacklisted:
            await self.blacklist_user(interaction, user, length, reason)
            await self.send_embed(interaction, user, "blacklisted")
            await self.send_webhook(interaction, user, length, reason)

    @blacklist.error
    async def blacklist_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral=True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
  await client.add_cog(Blacklist(client))