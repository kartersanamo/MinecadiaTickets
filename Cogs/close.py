from Assets.functions import seconds_to_format, is_found, get_data, is_ticket, execute, task, log_commands, log_tasks
from discord.ext import commands
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
try:
    from _analytics import logger as analytics
except ImportError:
    analytics = None
from discord import app_commands
import datetime
import requests
import discord
import asyncio
import time
import pytz

class Close(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client: commands.Bot = client
        self.data: dict = get_data()

    def convert_to_est(self, timestamp: str) -> str:
        """
        Converts a given timestamp from UTC unix to Eastern Standard Time (EST) in a readable format.

        Parameters:
        timestamp (str): The timestamp to be converted. It should be a string representation of a float or integer.

        Returns:
        str: The converted timestamp in the format "Day, Month DD, YYYY, HH:MM AM/PM EST".
            If an error occurs during the conversion, it logs the error and returns an empty string.
        """
        try:
            est_time = datetime.datetime.fromtimestamp(int(float(timestamp)), tz = pytz.utc).astimezone(pytz.timezone('US/Eastern'))
            return est_time.strftime('%a, %b %d, %Y, %I:%M:%S %p') + " EST"
        
        except Exception as error:
            log_commands.warning(f"Failed to convert the timestamp to EST {error}")

    @task("Get Transcript Link")
    async def return_link(self, content) -> str:
        """
        Sends a POST request to the paste.md-5.net API to create a new document with the given content.
        The function returns the URL of the created document.

        Parameters:
        content (str): The content to be sent to the paste.md-5.net API.

        Returns:
        str: The URL of the created document.
        """
        url: str = 'https://paste.minecadia.com/documents'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        response = requests.post(url, headers=headers, data = content.encode("utf-8"))
        response_data = response.json()
        key = response_data['key']
        return f"https://paste.minecadia.com/{key}"
        
        #url: str = 'https://paste.md-5.net/documents'
        #
        #try:
        #    async with aiohttp.ClientSession() as session:
        #        response = await session.post(url, data=content.encode("utf-8"))
        #        response_data = await response.json()
        #        key = response_data['key']
        #        return f"https://paste.md-5.net/{key}"
        #except aiohttp.ClientError as e:
        #    log_tasks.warning(f"Failed to get link: {e}")
        #except asyncio.TimeoutError:
        #    log_tasks.warning("Request to paste.md-5.net timed out.")
        #
        #return "https://paste.md-5.net/"

    @task("Fetch All Messages")
    async def fetch_all_messages(self, channel: discord.TextChannel) -> list[discord.Message]:
        """
        Fetches all messages from a given Discord text channel, including past messages. 
        This method is here to ensure that all messages are gathered FIRST, and then added to the transcript.
        If the messages are not grabbed first, then not all messages will be interated over in the case of a 
        ticket with a lot of messages, leading to transcripts being cut off.

        Parameters:
        channel (discord.TextChannel): The Discord text channel from which to fetch messages.

        Returns:
        list[discord.Message]: A list of all messages in the given channel, sorted by their creation time in ascending order.
        """
        return [message async for message in channel.history(limit = None, oldest_first = True)]

    @task("Format Embed")
    async def format_embed_content(self, embed: discord.Embed) -> str:
        """
        This function formats an embed into a string that can be used to create a transcript.
        It extracts the title, description, fields, and footer from the embed and formats them into a table-like structure.

        Parameters:
        embed (discord.Embed): The embed to be formatted.

        Returns:
        str: The formatted string representing the embed.
        """
        message_content = ""
        lengths = []
        dictionary = embed.to_dict()
        title = dictionary.get('title', '')
        description = dictionary.get('description', '')
        fields = dictionary.get('fields', [])
        footer = dictionary.get('footer', {}).get('text', '')
                
        if title:
            lengths.append(len(title))
        if description:
            for line in description.split("\n"):
                lengths.append(len(line))
        for field in fields:
            field_name = field.get('name', '')
            field_value = field.get('value', '')
            lengths.append(len(field_name))
            lengths.append(len(field_value))
        if footer:
            lengths.append(len(footer))
                
        if lengths:
            max_length = min(max(lengths), 100)
        else:
            return ""
                
        message_content += "/" + "-" * (int(max_length) + 2) + "\\\n"
        new_line = " "
        if title:
            message_content += f"| {title:{max_length}} |\n"
            message_content += f"| {new_line:{max_length}} |\n"
        if description:
            for line in description.split("\n"):
                substrings = []
                index = 0
                while index < len(line):
                    substrings.append(line[index : index + 100])
                    index += 100
                for sub in substrings:
                    message_content += f"| {sub:{max_length}} |\n"
            message_content += f"| {new_line:{max_length}} |\n"
        for field in fields:
            field_name = field.get('name', '')
            field_value = field.get('value', '')
            message_content += f"| {field_name:{max_length}} |\n{field_value:{max_length}} |\n"
        if footer:
            message_content += f"| {footer:{max_length}} |\n"
        message_content += "\\" + "-" * (int(max_length) + 2) + "/"

        return message_content

    @task("Generate Transcript Content")
    async def generate_transcript_content(self, messages: list[discord.Message], opened_string: str, ticket_type: str, ticket_number: str, owner: discord.Member, owner_id: int, reason: str, closed_by: discord.Member, channel_id: int, closed_at_string: str, closed_by_id: int) -> str:
        """
        This function generates a transcript content string from a list of Discord messages.

        Parameters:
        messages (list[discord.Message]): A list of Discord messages to be included in the transcript.
        opened_string (str): The opened timestamp in a readable format.
        ticket_type (str): The type of the ticket.
        ticket_number (str): The ticket number.
        owner (discord.Member): The owner of the ticket.
        owner_id (int): The ID of the owner of the ticket.
        reason (str): The reason for closing the ticket.
        closed_by (discord.Member): The member who closed the ticket.
        channel_id (int): The ID of the Discord channel.
        closed_at_string (str): The closed timestamp in a readable format.
        closed_by_id (int): The ID of the member who closed the ticket.

        Returns:
        str: The generated transcript content.
        """
        content: str = f"Minecadia Tickets Bot: {ticket_type}\n- Opened by: {owner} ({owner_id})\n- Opened at: {opened_string}\n- Channel ID: {channel_id}\n- Ticket ID: {ticket_number}\n \n──────────────────────────────────────────────────────\n \n"
        for message in messages:
            try:
                message_content: str = message.content
                for embed in message.embeds:
                    embed_content: str = await self.format_embed_content(embed)
                    message_content += "\n" + embed_content
                created_at = self.convert_to_est(message.created_at.timestamp())
                content += f"[{created_at}]\n{message.author.name} : {message.author.id}"
                if message_content:
                    content += f"\n\t{message_content}"
                content += "\n\n"

            except Exception as error:
                log_tasks.warning(f"Failed logging message {message.author} ({message.author.id}): {message.content} {error}")
        
        content += f"──────────────────────────────────────────────────────\n\n- Closure Reason: {reason}\n- Closed By: {closed_by} ({closed_by_id})\n- Closed At: {closed_at_string}"

        return content

    @task("Get Ticketlog Embed")
    async def get_ticket_log(self, reason: str, opened_timestamp: int, ticket_number: str, owner_mention: str, owner: discord.Member, link: str, ticket_type: str, closed_at_timestamp: int, closed_by: discord.Member) -> discord.Embed:
        """
        This function generates a Discord embed for a ticket log.

        Parameters:
        reason (str): The reason for closing the ticket.
        opened_timestamp (int): The timestamp of when the ticket was opened.
        ticket_number (str): The ticket number.
        owner_mention (str): The mention of the owner of the ticket.
        owner_id (int): The ID of the owner of the ticket.
        link (str): The link to the ticket transcript.
        ticket_type (str): The type of the ticket.
        closed_at_timestamp (int): The timestamp of when the ticket was closed.
        closed_by (discord.Member): The member who closed the ticket.

        Returns:
        discord.Embed: A Discord embed containing the ticket log information.
        """
        delta = "N/A"
        if opened_timestamp != "N/A":
            seconds = closed_at_timestamp - opened_timestamp
            delta = seconds_to_format(seconds)
        
        desc = f"`🎫` **{ticket_type} #{ticket_number}** was closed by {closed_by}\n **Reason:** {reason}\n **Owner:** {owner_mention} / {owner.name}\n **Ticket Duration:** {delta}\n[Ticket Transcript]({link})"
        embed = discord.Embed(
            color = discord.Color.from_str(self.data["EMBED_COLOR"]), 
            description = desc
        )
        from Assets.functions import get_embed_logo_url
        logo_url = get_embed_logo_url(self.data["LOGO"])
        embed.set_footer(text = self.data["FOOTER"], icon_url = logo_url)

        return embed
    
    @task("Send Ticketlog", False)
    async def send_ticket_log(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        embed: discord.Embed,
        privated: str,
    ) -> None:
        channel_json_string = (
            "ADMIN_TICKET_LOGS_ID"
            if privated == "Admin"
            else "MANAGEMENT_TICKET_LOGS_ID"
            if privated == "Management"
            else "TICKET_LOGS_ID"
        )
        ticket_log_channel_id = self.data["CHANNEL_IDS"][channel_json_string]
        ticket_log_channel = guild.get_channel(ticket_log_channel_id)
        await ticket_log_channel.send(
            embed=embed, file=discord.File("Assets/Logo.png")
        )

        tasks = [
            overwrite.create_dm()
            for overwrite in channel.overwrites
            if isinstance(overwrite, discord.Member)
            and not overwrite.bot
            and channel.permissions_for(overwrite).view_channel
        ]

        try:
            dm_channels = await asyncio.gather(*tasks)
            send_tasks = [
                dm.send(embed=embed, file=discord.File("Assets/Logo.png"))
                for dm in dm_channels
                if dm
            ]
            await asyncio.gather(*send_tasks)
        except Exception as error:
            log_tasks.warning(f"Failed to send ticket log: {error}")

    @task("Update Database")
    async def update_database(
        self,
        closed_by: discord.Member,
        reason: str,
        name: str,
        link: str,
        closed_at_timestamp: int,
        channel_id: int,
        closed_by_id: int,
    ) -> None:
        tickets_closed_stat = await is_found(closed_by, "tickets_closed")
        new_ticket_closed_stat: int = tickets_closed_stat + 1

        execute(
            f"UPDATE tickets SET active = 'False', closed_by = '{closed_by_id}', closed_at = '{closed_at_timestamp}', reason = '{reason}', name = '{name}', transcript = '{link}' WHERE channelID = '{channel_id}'"
        )
        execute(
            f"UPDATE statistics SET tickets_closed = '{new_ticket_closed_stat}' WHERE user_ID = '{closed_by_id}'"
        )
        if analytics:
            analytics.increment_total_stat(str(closed_by_id), "tickets_closed", 1)

    @task("Fetch Ticket Info")
    async def fetch_ticket_info(self, channelID: int) -> tuple:
        """
        Fetches ticket information from the database based on the channel ID.

        Parameters:
        channelID (int): The ID of the Discord channel.

        Returns:
        tuple: A tuple containing the owner of the ticket, their ID, their mention, 
        the opened timestamp, the opened timestamp in a readable format, the ticket number, 
        the ticket type, the ticket privacy status, the closed timestamp, and the closed timestamp in a readable format.
        """
        bot_account: discord.ClientUser = self.client.user
        info = (bot_account, bot_account.id, bot_account.mention, 0, "N/A", "0000", "Unknown", "", 0, "")
        row = execute(f"SELECT number, opened_at, privated, type, ownerID FROM tickets WHERE channelID = '{channelID}'")
        if row:
            row = row[0]
            opened_timestamp: int = int(float(row["opened_at"]))
            opened_string: str = self.convert_to_est(opened_timestamp)
            ticket_number: str = row["number"]
            privated: str = row["privated"]
            ticket_type: str = row["type"]
            owner: discord.Member = await self.client.fetch_user(int(row["ownerID"]))
            owner_id: int = owner.id
            owner_mention: str = owner.mention
            closed_at_timestamp: int = int(time.time())
            closed_at_string: str = self.convert_to_est(closed_at_timestamp)
            info = (owner, owner_id, owner_mention, opened_timestamp, opened_string, ticket_number, ticket_type, privated, closed_at_timestamp, closed_at_string)

        return info

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

    @is_ticket()
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10.0, key = lambda i: (i.channel_id, i.user.id))
    @app_commands.command(name = "close", description = "Closes the ticket channel")
    @app_commands.describe(reason = "The reason for closing the ticket")
    async def close(self, interaction: discord.Interaction, reason: str) -> None:
        """
        Closes the ticket channel.

        Parameters:
        interaction (discord.Interaction): The interaction object representing the command invocation.
        reason (str): The reason for closing the ticket.

        Returns:
        None
        """
        await self.close_command(interaction, reason)

    @task("Close Command", False)
    async def close_command(self, interaction: discord.Interaction, reason: str) -> None:
        await interaction.response.defer()
        if interaction.guild is None:
            return
        await self.close_ticket_channel(
            interaction.guild,
            interaction.channel,
            interaction.user,
            reason,
        )

    @task("Close Ticket Channel", False)
    async def close_ticket_channel(
        self,
        guild: discord.Guild,
        channel: discord.TextChannel,
        closed_by: discord.Member,
        reason: str,
    ) -> None:
        """Full /close flow — used by slash command and dashboard API."""
        start = time.perf_counter()
        messages = await self.fetch_all_messages(channel)
        channel_id = channel.id
        (
            owner,
            owner_id,
            owner_mention,
            opened_timestamp,
            opened_string,
            ticket_number,
            ticket_type,
            privated,
            closed_at_timestamp,
            closed_at_string,
        ) = await self.fetch_ticket_info(channel_id)

        name = channel.name
        reason = reason.replace("'", " ")
        closed_by_id = closed_by.id
        content = await self.generate_transcript_content(
            messages,
            opened_string,
            ticket_type,
            ticket_number,
            owner,
            owner_id,
            reason,
            closed_by,
            channel_id,
            closed_at_string,
            closed_by_id,
        )

        link = await self.return_link(content)

        embed = await self.get_ticket_log(
            reason,
            opened_timestamp,
            ticket_number,
            owner_mention,
            owner,
            link,
            ticket_type,
            closed_at_timestamp,
            closed_by,
        )
        await self.send_ticket_log(guild, channel, embed, privated)
        await self.update_database(
            closed_by,
            reason,
            name,
            link,
            closed_at_timestamp,
            channel_id,
            closed_by_id,
        )

        await channel.delete()

        ticket_count = await self.get_ticket_count()
        log_commands.info(
            f"Closed #{name} ({channel_id}) in {str(round((time.perf_counter() - start), 2))}s by {closed_by} ({closed_by_id}) {ticket_count}"
        )

    @close.error
    async def close_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        log_commands.error(f"/{interaction.command.name} error {error}")
        await interaction.followup.send(content = error, ephemeral = True) if interaction.response.is_done() else await interaction.response.send_message(content = error, ephemeral = True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Close(client))