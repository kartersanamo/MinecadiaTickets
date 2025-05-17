from Assets.functions import get_data, is_ticket, execute, log_commands, task
from discord.ext import commands
from discord import app_commands
import discord
import asyncio


class Move(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @task("Defer Response", False)
    async def defer_response(self, interaction: discord.Interaction) -> None:
        """
        Defer the response to the interaction.

        This function is used to defer the response to an interaction, allowing the bot to send a response later.
        This is useful when the bot needs to perform some asynchronous tasks before sending a response.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.

        Returns:
        - None: This function does not return any value.
        """
        await interaction.response.defer()

    @task("Check Blacklisted", False)
    async def check_blacklisted_category(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> bool:
        """
        Checks if the given category is blacklisted for ticket movement.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.
        - category (discord.CategoryChannel): The category channel to check for blacklisting.

        Returns:
        - bool: Returns True if the category is blacklisted, False otherwise. If the category is blacklisted, sends a warning message to the user and returns True.
        """
        if category.id in self.data['BLACKLISTED_MOVE_CATEGORIES']:
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to move a ticket to a blacklisted category {category} ({category.id})")
            await interaction.response.send_message(content = "`❌` Failed! You cannot move a ticket to this category!", ephemeral = True)
            return True
        return False

    @task("Check Category", False)
    async def check_ticket_category(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> bool:
        """
        Checks if the given category is a valid ticket category.

        This function verifies if the provided category is a valid ticket category by comparing its ID with the list of ticket category IDs stored in the bot's data.
        If the category is not a valid ticket category, it logs a warning message, sends a warning message to the user, and returns True.
        If the category is a valid ticket category, it returns False.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.
        - category (discord.CategoryChannel): The category channel to check for validity.

        Returns:
        - bool: Returns True if the category is not a valid ticket category, False otherwise.
        """
        if category.id not in self.data["TICKET_CATEGORIES"]:
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to move a ticket to a non-ticket category {category} ({category.id})")
            await interaction.response.send_message(content = "`❌` Failed! That is not a ticket category!", ephemeral = True)
            return True
        return False

    @task("Move Categories", False)
    async def move_categories(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        """
        Moves the ticket channel to a specified category.

        This function is responsible for moving the ticket channel to a new category. It takes an interaction object and a category channel as parameters.
        The interaction object provides context about the command invocation, while the category channel represents the destination for the ticket channel.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.
        - category (discord.CategoryChannel): The category channel to move the ticket channel to.

        Returns:
        - None: This function does not return any value. It updates the ticket channel's category in the Discord server.
        """
        await interaction.channel.edit(category = category)

    @task("Update Database", False)
    async def update_database(self, category_name: str, channel_id: int) -> None:
        """
        Updates the database with the new category and privacy settings for a ticket.

        This function takes a category name and a channel ID as parameters. It checks the category name and updates the corresponding fields in the 'tickets' table in the database.
        If the category name is "Admin+ Check", it sets the 'privated' field to 'Admin'.
        If the category name is "Store Issue Tickets", it sets the 'type' field to 'Store Issue Tickets' and the 'privated' field to 'Admin'.
        If the category name is "Management Contact", it sets the 'type' field to 'Management Contact' and the 'privated' field to 'Management'.
        For any other category name, it sets the 'type' field to the category name and the 'privated' field to an empty string-representing a non-privated ticket.

        Parameters:
        - category_name (str): The name of the category to update in the database.
        - channel_id (int): The ID of the channel associated with the ticket.

        Returns:
        - None: This function does not return any value. It updates the database directly.
        """
        if category_name == "Admin+ Check":
            execute(f"UPDATE tickets SET privated = 'Admin' WHERE channelID = '{channel_id}'")
        elif category_name == "Store Issue Tickets":
            execute(f"UPDATE tickets SET type = '{category_name}', privated = 'Admin' WHERE channelID = '{channel_id}'")
        elif category_name == "Management Contact":
            execute(f"UPDATE tickets SET type = '{category_name}', privated = 'Management' WHERE channelID = '{channel_id}'")
        else:
            execute(f"UPDATE tickets SET type = '{category_name}', privated = '' WHERE channelID = '{channel_id}'")

    @task("Set Permissions", False)
    async def set_permissions(self, interaction: discord.Interaction, new_category_id: int) -> None:
        """
        Sets the permissions for the ticket channel based on the existing overwrites.

        This function first retrieves the existing permission overwrites for the ticket channel. 
        It then syncs the permissions with the ticket category that it has been moved to.
        Then, it adds any permissions from the old overwrites that is for a discord.Member or for the default role.
        It also sets the 'view_channel' permission for the staff team to False. This is necessary so that the staff 
        team can view the category for the /move command, but not the tickets inside if they are not the proper role.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.

        Returns:
        - None: This function does not return any value. It updates the permissions for the ticket channel.
        """
        permissions = interaction.channel.overwrites.items()
        while interaction.channel.category.id != new_category_id:
            await asyncio.sleep(0.5)
        await interaction.channel.edit(sync_permissions = True)
        for key, value in permissions:
            if isinstance(key, discord.Member) or key == interaction.guild.default_role:
                await interaction.channel.set_permissions(key, overwrite = value)
        staff_team = interaction.guild.get_role(self.data['ROLE_IDS']['STAFF_TEAM_ROLE_ID'])
        await interaction.channel.set_permissions(staff_team, view_channel = False)

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, category_name: str) -> None:
        """
        Sends an embed message to the interaction response, confirming the ticket movement.

        This function creates an embed message with a description indicating the user who moved the ticket and the new category.
        It then sets the footer of the embed with the footer text and icon URL from the bot's data.
        Finally, it edits the original response of the interaction with the embed message.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.
        - category_name (str): The name of the category to which the ticket has been moved.

        Returns:
        - None: This function does not return any value. It sends a message to the interaction response.
        """
        confirmation_embed = discord.Embed(
            description = f"{interaction.user.mention} has moved this ticket to **{category_name}**", 
            color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        confirmation_embed.set_footer(text = self.data["FOOTER"], icon_url = self.data["LOGO"]) 
        await interaction.edit_original_response(embed = confirmation_embed)

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "move", description = "Moves a ticket to a new category")
    @app_commands.describe(category = "The category to move the ticket to")
    async def move(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        """
        Moves a ticket to a new category in a Discord server.

        This function is a command handler for the '/move' command in a Discord bot. It is designed to be used in a server with ticket management functionality.
        The function checks if the interaction is in a guild (server), verifies if the channel is a ticket channel, and then moves the ticket to a specified category.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.
        - category (discord.CategoryChannel): The category channel to move the ticket to.

        Returns:
        - None: This function does not return any value. It updates the ticket channel's category in the Discord server.
        """
        await self.move_command(interaction, category)

    @task("Move Command", True)
    async def move_command(self, interaction, category) -> None:
        """
        Executes the ticket movement process.

        This function is responsible for handling the ticket movement command. It checks if the specified category is valid and not blacklisted,
        and then proceeds to move the ticket to the new category, update the database, set the appropriate permissions, and send a confirmation message.

        Parameters:
        - interaction (discord.Interaction): The interaction object representing the context of the command invocation.
        - category (discord.CategoryChannel): The category channel to move the ticket to.

        Returns:
        - None: This function does not return any value. It updates the ticket channel's category in the Discord server.
        """
        blacklisted_category = await self.check_blacklisted_category(interaction, category)
        not_a_ticket_category = await self.check_ticket_category(interaction, category) 
        if not blacklisted_category and not not_a_ticket_category:
            await self.defer_response(interaction) 
            await self.move_categories(interaction, category)
            await self.update_database(category.name, interaction.channel.id)
            await self.set_permissions(interaction, category.id)
            await self.send_embed(interaction, category.name)

    @move.error
    async def move_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Move(client))