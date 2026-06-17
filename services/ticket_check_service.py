from discord import app_commands
import discord

from core.config import ConfigManager


class TicketCheckService:
    @staticmethod
    def ticket_only():
        async def predicate(interaction: discord.Interaction) -> bool:
            settings = ConfigManager.all()
            if (
                not interaction.channel.category if interaction.channel is not None and isinstance(interaction.channel, discord.TextChannel) and interaction.channel.category is not None else None
                or interaction.channel.category.id if interaction.channel is not None and isinstance(interaction.channel, discord.TextChannel) and interaction.channel.category is not None else None not in ConfigManager.get("TICKET_CATEGORIES")
            ):
                raise app_commands.CheckFailure(
                    "`❌` Failed! This command can only be ran inside of a ticket."
                )
            return True

        return app_commands.check(predicate)


is_ticket = TicketCheckService.ticket_only
