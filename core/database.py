from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from mysql.connector import pooling

from core.config import ConfigManager
from core.loggers import log_tasks

log = logging.getLogger("Tasks")

_DB_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tickets-db")


class DatabasePool:
    _instance: Optional["DatabasePool"] = None
    _pool: Optional[pooling.MySQLConnectionPool] = None

    @classmethod
    def get(cls) -> "DatabasePool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _pool_config(self) -> dict[str, Any]:
        cfg = ConfigManager.get_db_config()
        return {
            "host": cfg["host"],
            "port": cfg["port"],
            "user": cfg["user"],
            "password": cfg["password"],
            "database": cfg["database"],
            "autocommit": bool(cfg.get("autocommit", True)),
        }

    def _ensure_pool(self) -> pooling.MySQLConnectionPool:
        if self._pool is None:
            cfg = self._pool_config()
            self._pool = pooling.MySQLConnectionPool(
                pool_name="minecadia_tickets",
                pool_size=8,
                pool_reset_session=True,
                **cfg,
            )
        return self._pool

    def execute(self, query: str, params: tuple | None = None) -> list:
        rows: list = []
        connection = None
        try:
            connection = self._ensure_pool().get_connection()
            cursor = connection.cursor(dictionary=True)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if cursor.description:
                rows = cursor.fetchall()
            cursor.close()
        except Exception as error:
            from core.errors.db import DatabaseErrors

            DatabaseErrors.log_db_failure(log_tasks, error, query_hint=query)
        finally:
            if connection is not None:
                connection.close()
        return rows

    @classmethod
    def execute(cls, query: str, params: tuple | None = None) -> list:
        """Blocking query — use only from threads or sync code."""
        return cls.get().execute(query, params)

    @classmethod
    async def aexecute(cls, query: str, params: tuple | None = None) -> list:
        """Run a blocking query off the Discord event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_DB_EXECUTOR, cls.execute, query, params)

