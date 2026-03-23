from Assets.functions import get_data, log_tasks, log_commands, task
from discord import app_commands
from discord.ext import commands
import cachetools
import discord
import asyncio


class ActiveTickets(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()
        self.cache = cachetools.TTLCache(maxsize = self.data['ACTIVE_TICKETS_CACHE']['ENTRIES'], ttl = 60 * self.data['ACTIVE_TICKETS_CACHE']['MINUTES_TO_EXPIRE'])

    @task("Check User Messages", False)
    async def check_user_messages(self, user_id: int, channel: discord.TextChannel, tickets: list) -> None:
        """
        This function checks if a user has sent any messages in a specific ticket channel.
        If the user has sent a message, the channel's mention and category name are appended to the tickets list.
        The function uses a cache to avoid unnecessary API calls and improve performance.

        Parameters:
        - user_id (int): The ID of the user to check.
        - channel (discord.TextChannel): The text channel to check.
        - tickets (list): A list to store the tickets.

        Returns:
        - None: The function does not return anything. It modifies the tickets list directly.
        """
        cache_key: str = f"{user_id}-{channel.id}"
        if cache_key in self.cache:
            if self.cache[cache_key]:
                tickets.append(f"{channel.mention} {channel.category.name}")
            return

        try:
            async for message in channel.history(limit = None):
                if message.author.id == user_id:
                    tickets.append(f"{channel.mention} {channel.category.name}")
                    self.cache[cache_key] = True
                    return
            self.cache[cache_key] = False  

        except Exception as error:
            log_tasks.error(f"Checking user messages error {error}")
            self.cache[cache_key] = False

    @task("Get Tickets", True)
    async def get_tickets_list(self, interaction: discord.Interaction) -> list:
        """
        This function retrieves a list of tickets that the user is actively speaking in.
        It iterates through the specified ticket categories, checks each ticket channel for new messages,
        and appends the ticket's mention and category name to the tickets list if the user has sent a message.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object representing the command invocation.

        Returns:
        - tickets (list): A list of strings, where each string is a formatted mention and category name of a ticket channel.
        """
        tickets: list = []
        for category_id in self.data["TICKET_CATEGORIES"]:
            category = interaction.guild.get_channel(category_id)
            if category:
                tasks = [asyncio.create_task(self.check_user_messages(interaction.user.id, ticket, tickets)) for ticket in category.text_channels if ticket.permissions_for(interaction.user).read_messages]
                await asyncio.gather(*tasks)

        return tickets

    @task("Send Embed", False)
    async def send_embed(self, interaction: discord.Interaction, tickets: list) -> None:
        """
        This function sends an embed to the Discord interaction with a list of tickets.
        If the list is empty, it sends a message indicating no active tickets found.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object representing the command invocation.
        - tickets (list): A list of strings, where each string is a formatted mention and category name of a ticket channel.

        Returns:
        - None: The function does not return anything. It sends a Discord message using the interaction object.
        """
        description: str = "\n".join(tickets) if tickets else "No active tickets found"
        embed = discord.Embed(
            title = f"{interaction.user.name}'s Active Tickets",
            color = discord.Color.from_str(self.data["EMBED_COLOR"]),
            description = description
        )
        from Assets.functions import get_embed_logo_url
        logo_url = get_embed_logo_url(self.data["LOGO"])
        embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)
        await interaction.edit_original_response(content = None, embed = embed)

    @app_commands.guild_only()
    @app_commands.command(name="active-tickets", description="Returns which tickets you are actively speaking in")
    async def activetickets(self, interaction: discord.Interaction) -> None:
        """
        This function is a Discord slash command that retrieves and displays the tickets
        where the user is actively speaking in. It uses the `activetickets_command` method
        to perform the actual logic.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object representing the command invocation.

        Returns:
        - None: The function does not return anything. It sends a Discord message using the interaction object.
        """
        await self.activetickets_command(interaction)

    @task("ActiveTickets Command", True)
    async def activetickets_command(self, interaction: discord.Interaction) -> None:
        """
        This function is responsible for handling the execution of the 'activetickets' command in a Discord bot.
        It defers the response, retrieves a list of active tickets for the user, and sends an embed with the ticket information.

        Parameters:
        - interaction (discord.Interaction): The Discord interaction object representing the command invocation.

        Returns:
        - None: The function does not return anything. It sends a Discord message using the interaction object.
        """
        await interaction.response.defer()
        tickets: list = await self.get_tickets_list(interaction)
        await self.send_embed(interaction, tickets)

    @activetickets.error
    async def activetickets_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(ActiveTickets(client))