from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import mysql.connector
from mysql.connector import pooling

from core.config import ConfigLoader
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
        cfg = ConfigLoader.get()["DATABASE_CONFIG"]
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
            try:
                import sys
                from pathlib import Path

                root = Path(__file__).resolve().parent.parent.parent
                if str(root) not in sys.path:
                    sys.path.insert(0, str(root))
                from _errors.db import log_db_failure

                log_db_failure(log_tasks, error, query_hint=query)
            except ImportError:
                log_tasks.error("Error executing query: %s %s", query, error, exc_info=True)
        finally:
            if connection is not None:
                connection.close()
        return rows


def execute(query: str, params: tuple | None = None) -> list:
    """Blocking query — use only from threads or sync code. Prefer ``aexecute`` in async handlers."""
    return DatabasePool.get().execute(query, params)


async def aexecute(query: str, params: tuple | None = None) -> list:
    """Run a blocking query off the Discord event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_DB_EXECUTOR, execute, query, params)
