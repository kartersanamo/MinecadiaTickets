from discord import app_commands
import discord

from core.config import get_settings


class TicketCheckService:
    @staticmethod
    def ticket_only():
        async def predicate(interaction: discord.Interaction) -> bool:
            settings = get_settings()
            if (
                not interaction.channel.category
                or interaction.channel.category.id not in settings["TICKET_CATEGORIES"]
            ):
                raise app_commands.CheckFailure(
                    "`❌` Failed! This command can only be ran inside of a ticket."
                )
            return True

        return app_commands.check(predicate)


is_ticket = TicketCheckService.ticket_only
