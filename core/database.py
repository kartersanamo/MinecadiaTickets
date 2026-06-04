import mysql.connector

from core.config import get_settings
from core.loggers import log_tasks

_pool = None


def create_pool():
    global _pool
    data = get_settings()
    config = {
        "host": data["DATABASE_CONFIG"]["host"],
        "port": data["DATABASE_CONFIG"]["port"],
        "user": data["DATABASE_CONFIG"]["user"],
        "password": data["DATABASE_CONFIG"]["password"],
        "database": data["DATABASE_CONFIG"]["database"],
        "autocommit": bool(data["DATABASE_CONFIG"]["autocommit"]),
    }
    _pool = mysql.connector.connect(**config)


def execute(query: str) -> list:
    global _pool
    if _pool is None:
        create_pool()

    rows: list = []
    try:
        cursor = _pool.cursor(dictionary=True)
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
    except Exception as error:
        log_tasks.error(f"Error executing query: {query} {error}")
    return rows
