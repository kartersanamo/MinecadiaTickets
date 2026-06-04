import json
import os

from dotenv import load_dotenv

load_dotenv()

_settings: dict | None = None


def _db_config_from_env():
    if not os.getenv("DB_HOST"):
        return None
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "") or os.getenv("DB_DATABASE", ""),
        "autocommit": os.getenv("DB_AUTOCOMMIT", "true").lower() in ("1", "true", "yes"),
    }


def get_settings() -> dict:
    global _settings
    if _settings is not None:
        return _settings
    with open("Assets/config.json", "r") as file:
        data = json.load(file)
    if os.getenv("DISCORD_TOKEN"):
        data["TOKEN"] = os.getenv("DISCORD_TOKEN")
    if os.getenv("TICKET_BLACKLIST_WEBHOOK"):
        data["TICKET_BLACKLIST_WEBHOOK"] = os.getenv("TICKET_BLACKLIST_WEBHOOK")
    db = _db_config_from_env()
    if db is not None:
        data["DATABASE_CONFIG"] = db
    _settings = data
    return _settings


def get_data() -> dict:
    return get_settings()


def get_ticket_data() -> dict:
    with open("Assets/tickets.json", "r") as file:
        tickets = json.load(file)
    del tickets["TOGGLE_STATUS"]
    return tickets
