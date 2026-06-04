import discord

from core.database import DatabasePool


class StatisticsRepository:
    def __init__(self, db: DatabasePool | None = None):
        self._db = db or DatabasePool.get()

    async def find_row(self, user_id: int) -> list:
        return await self._db.execute(
            f"SELECT * FROM `statistics` WHERE `user_ID`='{user_id}'"
        )

    async def insert_default_row(self, user_id: int) -> None:
        await self._db.execute(
            f"INSERT INTO `statistics` (`user_ID`, `tickets_closed`, `messages_sent`, `warnings`, "
            f"`mutes`, `temp_bans`, `bans`, `screenshares`, `manual_bans`, `blacklists`, `revives`, "
            f"`appeals`, `threads_locked`, `strike_team_votes`, `characters_sent`, `punishment_requests`) "
            f"VALUES ('{user_id}', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')"
        )
