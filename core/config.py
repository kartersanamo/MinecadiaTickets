import json
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class ConfigLoader:
    _instance: Optional["ConfigLoader"] = None

    @classmethod
    def get(cls) -> dict:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.settings

    def __init__(self):
        with open("assets/config.json", "r") as file:
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

    def get_db_config(self) -> dict:
        if os.getenv("DB_HOST"):
            return self._db_config_from_env()
        return self.settings.get("DATABASE_CONFIG") or {}


def get_settings() -> dict:
    return ConfigLoader.get()


def get_data() -> dict:
    return get_settings()


def get_db_config() -> dict:
    return ConfigLoader().get_db_config()


def get_ticket_data() -> dict:
    with open("assets/tickets.json", "r") as file:
        tickets = json.load(file)
    del tickets["TOGGLE_STATUS"]
    return tickets
