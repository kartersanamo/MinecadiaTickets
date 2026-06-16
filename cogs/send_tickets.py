"""
send_tickets.py

This file is the cog for the send tickets command.
It is used to send a message prompt to the ticket channel.

Copyright (c) 2026 Karter Sanamo
License: MIT
"""
from discord.ext import commands
from discord import app_commands
from typing import Literal
import discord
from core.config import ConfigManager
from core.decorators import task
from ui.views.ticket_logs_view import TicketLogs
from ui.views.tickets_view import TicketsView
from ui.views.tickets_view2_view import TicketsView2

class TicketsSend(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client: commands.Bot = client
    @app_commands.guild_only() 
    @app_commands.command(name = "send-tickets", description = "Sends a message prompt.")
    @app_commands.describe(option = "The message that you'd wish to send")
    async def send_tickets(self, interaction: discord.Interaction, option: Literal["Tickets"], channel: discord.TextChannel = None) -> None:
        await self.send_tickets_command(interaction, option, channel if channel else interaction.channel)

    @task("SendTickets Command", True)
    async def send_tickets_command(self, interaction: discord.Interaction, option: str, channel: discord.TextChannel) -> None:
        None if interaction.response.is_done() else await interaction.response.send_message(content = "`🔃` Sending your message...", ephemeral = True)

        embeds = {
            "Tickets": [
                {
                    "embed": discord.Embed(
                        color = discord.Color.from_str(ConfigManager.get("EMBED_COLOR")), 
                        description = ("**Select a category that best represents your ticket reasoning**:\n\n"
                                       ""
                                       "**-** Be sure to be as specific and detailed as possible in your ticket.\n"
                                       "**-** Any visual evidence should be uploaded to [Imgur](https://imgur.com/upload) & [YouTube](https://www.youtube.com/).\n"
                                       "**-** A staff member will be with you as soon as possible.")
                    ),
                    "view": TicketsView(),
                    "image": "https://i.imgur.com/k93vtvB.png"
                },
                {
                    "embed": None,
                    "view": TicketsView2(),
                    "image": None
                },
                {
                    "embed": discord.Embed(
                        color = discord.Color.from_str(ConfigManager.get("EMBED_COLOR")),
                        description = "**Want to see your previous tickets? Click the envelope down below!**"
                    ),
                    "view": TicketLogs(),
                    "image": None
                }
            ]
        }
        chosen_message: list[dict] = embeds.get(option, [])
        for message in chosen_message:
            embed = message['embed']
            if message['image']:
                embed.set_image(url = message['image'])
            await channel.send(embed = embed, view = message['view'])
        
        await interaction.edit_original_response(content = "`✅` Successfully sent your message prompt!")



async def setup(client: commands.Bot) -> None:
    await client.add_cog(TicketsSend(client))