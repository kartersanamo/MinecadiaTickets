from repositories.ticket_repository import TicketRepository


class TicketService:
    def __init__(self, repository: TicketRepository | None = None, settings: dict | None = None):
        self._repo = repository or TicketRepository()
        self.settings = settings or {}

    def execute(self, query: str) -> list:
        return self._repo.execute(query)
