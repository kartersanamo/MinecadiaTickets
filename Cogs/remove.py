from Assets.functions import get_data, is_ticket, log_commands, task
from discord.ext import commands
from discord import app_commands
import discord

class Remove(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client = client
        self.data: dict = get_data()

    @task("Get Role Level", False)
    async def get_role_level(self, role_id: int) -> int:
        """
        This function retrieves the level of a role based on its ID. This works by iterating through the role hierarchy dictionary
        and comparing the role IDs- where each next level of roles in the dictionary is higher than the previous.

        Parameters:
        role_id (int): The ID of the role for which to retrieve the level.

        Returns:
        int: The level of the role. If the role ID is not found in the role hierarchy, returns -1.
        """
        for level, roles in enumerate(self.data['ROLE_HIERARCHY'].values()):
            if role_id in roles:
                return level

    @task("Is Higher Rank", False)
    async def is_higher_rank(self, role_id1: int, role_id2: int) -> bool:
        """
        This function compares the levels of two roles based on their IDs. It determines if the first role is higher in the role hierarchy than the second.

        Parameters:
        role_id1 (int): The ID of the first role to compare.
        role_id2 (int): The ID of the second role to compare.

        Returns:
        bool: True if the first role is higher in the role hierarchy than the second, False otherwise.
        """
        level1: int = await self.get_role_level(role_id1)
        level2: int = await self.get_role_level(role_id2)
        return level1 > level2

    @task("Remove Permissions", False)
    async def remove_permissions(self, channel: discord.TextChannel, user: discord.Member) -> None:
        """
        This function removes a user's permission to view a specific text channel.

        Parameters:
        channel (discord.TextChannel): The text channel from which to remove the user's permission.
        user (discord.Member): The user whose permission to view the channel is to be removed.

        Returns:
        None: This function is an asynchronous coroutine and does not return any value.
        """
        perms = channel.overwrites_for(user)
        perms.view_channel = False
        await channel.set_permissions(user, overwrite = perms)

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function sends an embed message to the interaction channel, detailing the removal of a user from a ticket.

        Parameters:
        interaction (discord.Interaction): The interaction object that triggered this function.
        user (discord.Member): The user who was removed from the ticket.

        Returns:
        None: This function is an asynchronous coroutine and does not return any value.
        """
        embed = discord.Embed(
            color = discord.Color.from_str(self.data["EMBED_COLOR"]),
            description = f"{interaction.user.mention} has removed {user.mention} from the ticket {interaction.channel.mention}"
        )
        from Assets.functions import get_embed_logo_url
        logo_url = get_embed_logo_url(self.data["LOGO"])
        embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
        await interaction.response.send_message(embed = embed, file = discord.File("Assets/Logo.png"))

    @task("Check Higher Rank", False)
    async def check_higher_rank(self, interaction: discord.Interaction, user: discord.Member) -> bool:
        """
        This function checks if the user trying to remove another staff member is higher in the role hierarchy.
        If the user is a staff member and trying to remove another staff member who is higher in the hierarchy,
        it logs a warning and sends an ephemeral message to the user.

        Parameters:
        interaction (discord.Interaction): The interaction object that triggered this function.
        user (discord.Member): The user who is being checked for higher rank.

        Returns:
        bool: Returns True if the user trying to remove is higher in the role hierarchy, False otherwise.
        """
        staff_team_role: discord.Role = interaction.guild.get_role(self.data['ROLE_IDS']['STAFF_TEAM_ROLE_ID'])
        if staff_team_role in user.roles:
            disregard_role_ids: list[int] = self.data['DISREGARD_REMOVE_COMMAND_ROLE_IDS']
            role_id_1: int = user.top_role.id if user.top_role.id not in disregard_role_ids else user.roles[-2].id
            role_id_2: int = interaction.user.top_role.id if interaction.user.top_role.id not in disregard_role_ids else interaction.user.roles[-2].id
            if await self.is_higher_rank(role_id_1, role_id_2):
                log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to remove a staff member higher than them {user} ({user.id})")
                await interaction.response.send_message(content = "You cannot remove a staff member who is higher than you!", ephemeral = True)
                return True
        return False

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "remove", description = "Removes a user from the ticket")
    @app_commands.describe(user = "The user to remove from the ticket")
    async def remove(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function is a Discord slash command that removes a user from a ticket.
        It checks if the interaction is in a guild and if the command is being used in a ticket channel.
        If the conditions are met, it calls the `remove_command` method to perform the actual removal.

        Parameters:
        interaction (discord.Interaction): The interaction object that triggered this function.
        user (discord.Member): The user to be removed from the ticket.

        Returns:
        None: This function is an asynchronous coroutine and does not return any value.
        """
        await self.remove_command(interaction, user)

    @task("Remove Command", True)
    async def remove_command(self, interaction: discord.Interaction, user: discord.Member) -> None:
        """
        This function is responsible for removing a user from a ticket. It checks if the user trying to remove is higher in the role hierarchy
        and logs a warning if they are. If the user is not higher in the hierarchy, it removes the user's permission to view the ticket channel
        and sends an embed message to the interaction channel detailing the removal.

        Parameters:
        interaction (discord.Interaction): The interaction object that triggered this function. This object contains information about the command, user, and channel.
        user (discord.Member): The user to be removed from the ticket. This user is a member of the Discord server.

        Returns:
        None: This function is an asynchronous coroutine and does not return any value.
        """
        removing_higher: bool = await self.check_higher_rank(interaction, user)
        if not removing_higher:
            await self.remove_permissions(interaction.channel, user)
            await self.send_embed(interaction, user)

    @remove.error
    async def remove_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Remove(client))