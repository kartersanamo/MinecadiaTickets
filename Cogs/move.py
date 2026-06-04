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
        await interaction.response.defer()

    @task("Check Blacklisted", False)
    async def check_blacklisted_category(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> bool:
        if category.id in self.data['BLACKLISTED_MOVE_CATEGORIES']:
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to move a ticket to a blacklisted category {category} ({category.id})")
            await interaction.response.send_message(content = "`❌` Failed! You cannot move a ticket to this category!", ephemeral = True)
            return True
        return False

    @task("Check Category", False)
    async def check_ticket_category(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> bool:
        if category.id not in self.data["TICKET_CATEGORIES"]:
            log_commands.warning(f"{interaction.user} ({interaction.user.id}) tried to move a ticket to a non-ticket category {category} ({category.id})")
            await interaction.response.send_message(content = "`❌` Failed! That is not a ticket category!", ephemeral = True)
            return True
        return False

    @task("Move Categories", False)
    async def move_categories(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        await interaction.channel.edit(category = category)

    @task("Update Database", False)
    async def update_database(self, category_name: str, channel_id: int) -> None:
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
        confirmation_embed = discord.Embed(
            description = f"{interaction.user.mention} has moved this ticket to **{category_name}**", 
            color = discord.Color.from_str(self.data["EMBED_COLOR"])
        )
        from Assets.functions import get_embed_logo_url
        logo_url = get_embed_logo_url(self.data["LOGO"])
        confirmation_embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url) 
        await interaction.edit_original_response(embed = confirmation_embed)

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.command(name = "move", description = "Moves a ticket to a new category")
    @app_commands.describe(category = "The category to move the ticket to")
    async def move(self, interaction: discord.Interaction, category: discord.CategoryChannel) -> None:
        await self.move_command(interaction, category)

    @task("Move Command", True)
    async def move_command(self, interaction, category) -> None:
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