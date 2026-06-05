from discord.ext import commands
from discord import app_commands
import discord
import asyncio
from core.config import ConfigManager
from core.database import execute
from core.decorators import task
from core.loggers import log_tasks
from services.ticket_check_service import is_ticket

class Private(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "private", description = "Privates the ticket channel so that only Admins can view it")
    async def private(self, interaction: discord.Interaction) -> None:
        await self.private_command(interaction)

    @task("Change Category", False)
    async def change_category(self, channel: discord.TextChannel, category: discord.CategoryChannel) -> None:
        await channel.edit(category = category)

    @task("Update Database", False)
    async def update_database(self, channel_id: int, privated_str: str) -> None:
        execute(
            "UPDATE tickets SET privated = %s WHERE channel_id = %s",
            (privated_str, channel_id),
        )

    @task("Update Permissions", False)
    async def update_permissions(self, channel: discord.TextChannel, guild: discord.Guild, permissions, default_role: discord.Role) -> None:
        await channel.edit(sync_permissions = True)
        for key, value in permissions:
            if isinstance(key, discord.Member) or key == default_role:
                await channel.set_permissions(key, overwrite = value)
        staff_team: discord.Role = guild.get_role(ConfigManager.get('ROLE_IDS')['STAFF_TEAM_ROLE_ID'])
        await channel.set_permissions(staff_team, view_channel = False)

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, description: str) -> None:
        embed = discord.Embed(
            color = discord.Color.from_str(ConfigManager.get("EMBED_COLOR")), 
            description = f"{interaction.user.mention} {description}"
        )
        logo_url = self.client.app.embeds.get_logo_url(ConfigManager.get("LOGO"))
        embed.set_footer(text = ConfigManager.get('FOOTER'), icon_url = logo_url)
        await interaction.followup.send(embed = embed, file = discord.File("assets/Logo.png"))

    @task("Private Command", True)
    async def private_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        category: discord.CategoryChannel = interaction.guild.get_channel(ConfigManager.get('CHANNEL_IDS')['ADMIN+_CHECK_ID'])
        
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
        await self.management_command(interaction)

    @task("Management Command", True)
    async def management_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        category: discord.CategoryChannel = interaction.guild.get_channel(ConfigManager.get('CHANNEL_IDS')['MANAGEMENT_CONTACT_ID'])
        
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


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Private(client))