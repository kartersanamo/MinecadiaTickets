from services.statistics_service import StatisticsService

_svc = StatisticsService()

def is_found(user_id, statistic: str):
    rows = _svc._repo.find_row(user_id)
    if rows:
        return rows[0][statistic]
    _svc._repo.insert_default_row(user_id)
    return 0
