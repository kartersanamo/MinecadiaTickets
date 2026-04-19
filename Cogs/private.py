from Assets.functions import get_data, is_ticket, execute, log_commands, log_tasks, task
from discord.ext import commands
from discord import app_commands
import discord
import asyncio

class Private(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "private", description = "Privates the ticket channel so that only Admins can view it")
    async def private(self, interaction: discord.Interaction) -> None:
        """
        This function is a Discord interaction command that makes a ticket channel private.
        Only users with the ticket role can use this command.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
            This object contains information about the user, guild, and channel where the command was invoked.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        await self.private_command(interaction)

    @task("Change Category", False)
    async def change_category(self, channel: discord.TextChannel, category: discord.CategoryChannel) -> None:
        """
        This function is an asynchronous task that changes the category of a given text channel.

        Parameters:
        channel (discord.TextChannel): The text channel whose category needs to be updated.
        category (discord.CategoryChannel): The new category to which the text channel should be moved.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        await channel.edit(category = category)

    @task("Update Database", False)
    async def update_database(self, channel_id: int, privated_str: str) -> None:
        """
        This function is an asynchronous task that updates the 'privated' column in the 'tickets' table of the database.
        It sets the 'privated' column value to the provided 'privated_str' for the ticket channel identified by 'channel_id'.

        Parameters:
        channel_id (int): The unique identifier of the ticket channel in the database.
        privated_str (str): The new value to be set for the 'privated' column in the database.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        execute(f"UPDATE tickets SET privated = '{privated_str}' WHERE channelID = '{channel_id}'")

    @task("Update Permissions", False)
    async def update_permissions(self, channel: discord.TextChannel, guild: discord.Guild, permissions, default_role: discord.Role) -> None:
        """
        This function is an asynchronous task that updates the permissions of a given text channel.
        It sets the permissions for each key-value pair in the 'permissions' dictionary.
        If the key is a discord.Member or the default_role, it sets the overwrite permissions for that key.
        Additionally, it removes the view_channel permission for the staff_team role.

        Parameters:
        channel (discord.TextChannel): The text channel whose permissions need to be updated.
        guild (discord.Guild): The guild in which the text channel resides.
        permissions (dict): A dictionary containing the keys (discord.Member or discord.Role) and values (discord.PermissionOverwrite)
            representing the permissions to be set for each key.
        default_role (discord.Role): The default role for the guild.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        await channel.edit(sync_permissions = True)
        for key, value in permissions:
            if isinstance(key, discord.Member) or key == default_role:
                await channel.set_permissions(key, overwrite = value)
        staff_team: discord.Role = guild.get_role(self.data['ROLE_IDS']['STAFF_TEAM_ROLE_ID'])
        await channel.set_permissions(staff_team, view_channel = False)

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, description: str) -> None:
        """
        This function is an asynchronous task that sends an embed message to the interaction response.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
            This object contains information about the user, guild, and channel where the command was invoked.
        description (str): The description text to be included in the embed message.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        embed = discord.Embed(
            color = discord.Color.from_str(self.data["EMBED_COLOR"]), 
            description = f"{interaction.user.mention} {description}"
        )
        from Assets.functions import get_embed_logo_url
        logo_url = get_embed_logo_url(self.data["LOGO"])
        embed.set_footer(text = self.data['FOOTER'], icon_url = logo_url)
        await interaction.followup.send(embed = embed, file = discord.File("Assets/Logo.png"))

    @task("Private Command", True)
    async def private_command(self, interaction: discord.Interaction) -> None:
        """
        This function is an asynchronous task that handles the private command for ticket channels.
        It changes the category of the ticket channel, updates the database, sets permissions, and sends an embed message.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
            This object contains information about the user, guild, and channel where the command was invoked.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        await interaction.response.defer()
        category: discord.CategoryChannel = interaction.guild.get_channel(self.data['CHANNEL_IDS']['ADMIN+_CHECK_ID'])
        
        await self.change_category(interaction.channel, category)
        await self.update_database(interaction.channel.id, 'Admin')

        def check(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> bool:
            return after.id == interaction.channel.id and after.category == category
        try:
            await interaction.client.wait_for('guild_channel_update', check = check, timeout = 5)
        except asyncio.TimeoutError:
            if interaction.channel.category.id != category.id:
                log_tasks.warning("Timeout occurred while waiting for the category to update.")
                return await interaction.followup.send("`❌` Timeout Error! The bot could not change the channel's category. Please try again.", ephemeral = True)
        
        await self.update_permissions(interaction.channel, interaction.guild, interaction.channel.overwrites.items(), interaction.guild.default_role)
        await self.send_embed(interaction, "has turned this channel private.")

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "management", description = "Privates the channel so that only Management can view it")
    async def management(self, interaction: discord.Interaction) -> None:
        """
        This function is a Discord interaction command that makes a ticket channel private for Management only.
        Only users with the ticket role can use this command.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
            This object contains information about the user, guild, and channel where the command was invoked.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        await self.management_command(interaction)

    @task("Management Command", True)
    async def management_command(self, interaction: discord.Interaction) -> None:
        """
        This function is an asynchronous task that handles the management command for ticket channels.
        It changes the category of the ticket channel, updates the database, sets permissions, and sends an embed message.

        Parameters:
        interaction (discord.Interaction): The Discord interaction object that triggered this function.
            This object contains information about the user, guild, and channel where the command was invoked.

        Returns:
        None: This function does not return any value. It is an asynchronous function that performs an action.
        """
        await interaction.response.defer()
        category: discord.CategoryChannel = interaction.guild.get_channel(self.data['CHANNEL_IDS']['MANAGEMENT_CONTACT_ID'])
        
        await self.change_category(interaction.channel, category)
        await self.update_database(interaction.channel.id, 'Management')

        def check(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> bool:
            return after.id == interaction.channel.id and after.category == category
        try:
            await interaction.client.wait_for('guild_channel_update', check = check, timeout = 5)
        except asyncio.TimeoutError:
            if interaction.channel.category.id != category.id:
                log_tasks.warning("Timeout occurred while waiting for the category to update.")
                return await interaction.followup.send("`❌` Timeout Error! The bot could not change the channel's category. Please try again.", ephemeral = True)
        
        await self.update_permissions(interaction.channel, interaction.guild, interaction.channel.overwrites.items(), interaction.guild.default_role)
        await self.send_embed(interaction, "has made this channel for management.")

    @private.error
    async def private_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)
    
    @management.error
    async def management_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Private(client))