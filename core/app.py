from discord.ext import commands

from core.config import ConfigLoader
from core.database import DatabasePool
from repositories.statistics_repository import StatisticsRepository
from repositories.ticket_repository import TicketRepository
from services.statistics_service import StatisticsService
from services.ticket_service import TicketService


class BotApp:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = ConfigLoader.get()
        self.db = DatabasePool.get()
        self.statistics_repo = StatisticsRepository(self.db)
        self.statistics = StatisticsService(self.statistics_repo)
        self.tickets_repo = TicketRepository(self.db)
        self.tickets = TicketService(self.tickets_repo, self.settings)

    @classmethod
    def from_bot(cls, bot: commands.Bot) -> "BotApp":
        return cls(bot)
