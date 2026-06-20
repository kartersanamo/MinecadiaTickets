from core.bot_client import TicketsBot

from core.config import ConfigManager
from core.database import DatabasePool
from repositories.statistics_repository import StatisticsRepository
from repositories.ticket_repository import TicketRepository
from services.embed_service import EmbedService
from services.statistics_service import StatisticsService
from services.ticket_check_service import TicketCheckService
from services.ticket_service import TicketService
from services.time_format_service import TimeFormatService


class BotApp:
    def __init__(self, bot: TicketsBot):
        self.bot = bot
        self.settings = ConfigManager.all()
        self.db = DatabasePool.get()
        self.statistics_repo = StatisticsRepository(self.db)
        self.statistics = StatisticsService(self.statistics_repo)
        self.tickets_repo = TicketRepository(self.db)
        self.tickets = TicketService(self.tickets_repo, self.settings)
        self.ticket_checks = TicketCheckService()
        self.embeds = EmbedService()
        self.time_format = TimeFormatService()

    @classmethod
    def from_bot(cls, bot: TicketsBot) -> "BotApp":
        return cls(bot)
