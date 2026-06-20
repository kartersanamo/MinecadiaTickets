import json
import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


class ConfigManager:
    """Singleton access to bot configuration."""

    _instance: Optional["ConfigManager"] = None
    _extra_files: dict[str, dict] = {}
    _tickets: Optional[dict] = None

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        settings = cls.get_instance().settings
        if "." not in key:
            return settings.get(key, default)
        value: Any = settings
        for part in key.split("."):
            if not isinstance(value, dict):
                return default
            value = value.get(part)
            if value is None:
                return default
        return value

    @classmethod
    def all(cls) -> dict:
        return dict(cls.get_instance().settings)

    @classmethod
    def get_db_config(cls) -> dict:
        return cls.get_instance()._resolve_db_config()

    @classmethod
    def tickets(cls) -> dict:
        if cls._tickets is None:
            cls._tickets = cls._read_tickets_file()
        return cls._tickets

    @classmethod
    def _read_tickets_file(cls) -> dict:
        with open("assets/tickets.json", encoding="utf-8") as handle:
            data = json.load(handle)
        data.pop("TOGGLE_STATUS", None)
        return data

    @classmethod
    async def reload_tickets(cls) -> dict:
        """Reload ticket types from disk (used by manage-tickets UI after edits)."""
        import asyncio

        cls._tickets = await asyncio.to_thread(cls._read_tickets_file)
        return cls._tickets

    def __init__(self):
        with open("assets/config.json", encoding="utf-8") as file:
            data = json.load(file)
        if os.getenv("DISCORD_TOKEN"):
            data["TOKEN"] = os.getenv("DISCORD_TOKEN")
        if os.getenv("TICKET_BLACKLIST_WEBHOOK"):
            data["TICKET_BLACKLIST_WEBHOOK"] = os.getenv("TICKET_BLACKLIST_WEBHOOK")
        if os.getenv("DB_HOST"):
            data["DATABASE_CONFIG"] = self._db_config_from_env()
        self.settings = data

    @staticmethod
    def _db_config_from_env() -> dict:
        return {
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", ""),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "") or os.getenv("DB_DATABASE", ""),
            "autocommit": os.getenv("DB_AUTOCOMMIT", "true").lower() in ("1", "true", "yes"),
        }

    def _resolve_db_config(self) -> dict:
        if os.getenv("DB_HOST"):
            return self._db_config_from_env()
        return self.settings.get("DATABASE_CONFIG") or {}


__all__ = ["ConfigManager"]
