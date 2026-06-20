import discord

from repositories.statistics_repository import StatisticsRepository


class StatisticsService:
    def __init__(self, repository: StatisticsRepository | None = None):
        self._repo = repository or StatisticsRepository()

    async def get_statistic(self, user: discord.Member, statistic: str):
        rows = self._repo.find_row(user.id)
        if rows:
            return rows[0][statistic]
        self._repo.insert_default_row(user.id)
        return 0

    async def ensure_row(self, user: discord.Member) -> None:
        if not self._repo.find_row(user.id):
            self._repo.insert_default_row(user.id)


_default_statistics = StatisticsService()
is_found = _default_statistics.get_statistic
