from core.database import DatabasePool


class TicketRepository:
    def __init__(self, db: DatabasePool | None = None):
        self._db = db or DatabasePool.get()

    def execute(self, query: str) -> list:
        return self._db.execute(query)

    def find_active_by_channel(self, channel_id: int) -> list:
        return self._db.execute(
            f"SELECT * FROM `tickets` WHERE `channel_id`='{channel_id}' AND `active`='1'"
        )
