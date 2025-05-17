from Assets.functions import get_data, is_ticket, execute, log_commands, task
from discord.ext import commands
from discord import app_commands
import discord


class Add(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @task("Check Blacklisted", False)
    async def check_blacklisted(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        """
        Checks if a user is blacklisted for ticket access. If the user is blacklisted, it logs a warning message, sends an ephemeral message to the interaction channel, and returns True. Otherwise, it returns False.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        user (discord.Member): The user to check if they are blacklisted.

        Returns:
        bool: True if the user is blacklisted, False otherwise.
        """
        rows = execute(f"SELECT 1 FROM blacklists WHERE userID = {user.id} LIMIT 1")
        if rows:
            log_commands.warning(f"Failed to add {user} ({user.id}) to #{interaction.channel.name} ({interaction.channel.id}) as they are ticket blacklisted")
            await interaction.response.send_message(content = "`❌` Failed! You cannot add this player to the ticket as they are currently ticket blacklisted!", ephemeral = True)
            return True
        return False

    @task("Check Timed Out", False)    
    async def check_timed_out(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        """
        Checks if a user is currently timed out. If the user is timed out, it logs a warning message, sends an ephemeral message to the interaction channel, and returns True. Otherwise, it returns False.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        user (discord.Member): The user to check if they are timed out.

        Returns:
        bool: True if the user is timed out, False otherwise.
        """
        if user.is_timed_out():
            log_commands.warning(f"Failed to add {user} ({user.id}) to #{interaction.channel.name} ({interaction.channel.id}) as they are timed out")
            await interaction.response.send_message(content = "`❌` Failed! You cannot add this player to the ticket as they are currently timed out!", ephemeral = True)
            return True
        return False

    @task("Set Permissions", False)
    async def set_permissions(self, channel: discord.TextChannel, user: discord.Member) -> None:
        """
        Sets the necessary permissions for a user in a given Discord text channel.
        This function sets the "View Channel" and "Send Messages" permissions for the specified user in the given Discord text channel.
        Effectively adding the user to the ticket.

        Parameters:
        channel (discord.TextChannel): The Discord text channel where the permissions will be set.
        user (discord.Member): The Discord member for whom the permissions will be set.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        perms = channel.overwrites_for(user)
        perms.view_channel = True
        perms.send_messages = True
        await channel.set_permissions(user, overwrite=perms)

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function sends an embed message to the Discord interaction channel, containing information about adding a user to a ticket.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
        user (discord.Member): The user who is being added to the ticket.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        embed = discord.Embed(
            color = discord.Color.from_str(self.data["EMBED_COLOR"]), 
            description = f"{interaction.user.mention} has added {user.mention} to the ticket {interaction.channel.mention}"
        )
        embed.set_footer(text = self.data["FOOTER"], icon_url = self.data["LOGO"])
        await interaction.response.send_message(embed = embed)

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "add", description = "Adds a user to the ticket")
    @app_commands.describe(user = "The user to add to the ticket")
    async def add(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function is used to add a user to the ticket. It is a command for the Discord bot.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this command.
        user (discord.Member): The user to be added to the ticket.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        await self.add_command(interaction, user)

    @task("Add Command", True)
    async def add_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function is responsible for adding a user to the ticket, based on certain conditions.
        The function first checks if the user is blacklisted or timed out. If not, it sets the necessary 
        permissions for the user in the ticket channel (adding them) and sends an embed message.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this command.
        user (discord.Member): The user to be added to the ticket.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        blacklisted: bool = await self.check_blacklisted(interaction, user)
        timed_out: bool = await self.check_timed_out(interaction, user)
        
        if not blacklisted and not timed_out:
            await self.set_permissions(interaction.channel, user)
            await self.send_embed(interaction, user)

    @add.error
    async def add_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Add(client))