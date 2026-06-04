import mysql.connector
from typing import Optional

from core.config import ConfigLoader
from core.loggers import log_tasks


class DatabasePool:
    _instance: Optional["DatabasePool"] = None

    @classmethod
    def get(cls) -> "DatabasePool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self):
        cfg = ConfigLoader.get()["DATABASE_CONFIG"]
        return mysql.connector.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            autocommit=bool(cfg.get("autocommit", True)),
        )

    def execute(self, query: str) -> list:
        rows = []
        connection = None
        try:
            connection = self.connect()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
        except Exception as error:
            log_tasks.error(f"Error executing query: {query} {error}")
        finally:
            if connection:
                connection.close()
        return rows


def execute(query: str) -> list:
    return DatabasePool.get().execute(query)
