from discord import app_commands
import mysql.connector
import discord
import logger
import json
import time
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Variables that represent loggers that can be accessed anywhere in the bot's code simply by importing the logger
# Then you can run i.e `log_tasks.info("...")` to log information under the logger of "Tasks"
log_tasks = logger.logging.getLogger("Tasks")
log_commands = logger.logging.getLogger("Commands")

# Connection pool global variable
pool = None

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

def get_data() -> dict:
    with open("Assets/config.json", "r") as file:
        data = json.load(file)
    if os.getenv("DISCORD_TOKEN"):
        data["TOKEN"] = os.getenv("DISCORD_TOKEN")
    if os.getenv("TICKET_BLACKLIST_WEBHOOK"):
        data["TICKET_BLACKLIST_WEBHOOK"] = os.getenv("TICKET_BLACKLIST_WEBHOOK")
    db = _db_config_from_env()
    if db is not None:
        data["DATABASE_CONFIG"] = db
    return data
data = get_data()

def create_pool():
    global pool
    config = {
        "host": data["DATABASE_CONFIG"]["host"],
        "port": data["DATABASE_CONFIG"]["port"],
        "user": data["DATABASE_CONFIG"]["user"],
        "password": data["DATABASE_CONFIG"]["password"],
        "database": data["DATABASE_CONFIG"]["database"],
        "autocommit": bool(data["DATABASE_CONFIG"]["autocommit"]),
    }
    pool = mysql.connector.connect(**config)

def execute(query: str) -> list:
    global pool
    if pool is None:
        create_pool()
    
    rows: list = []
    try:
        connection = pool
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
    except Exception as error:
        log_tasks.error(f"Error executing query: {query} {error}")
    return rows

def task(action_name: str, log: bool = None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                time_elapsed = round((time.perf_counter() - start_time), 2)
                if time_elapsed > 3:
                    log_tasks.warning(f"{action_name} took a long time to complete and finished in {time_elapsed}s")
                elif log:
                    log_tasks.info(f"{action_name} completed in {time_elapsed}s")
                return result
            except Exception as error:
                log_tasks.error(f"{action_name} failed after {str(round((time.perf_counter() - start_time), 2))}s : {error}")
                raise error
        return wrapper
    return decorator

def is_ticket():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.channel.category or interaction.channel.category.id not in data['TICKET_CATEGORIES']:
            raise app_commands.CheckFailure("`❌` Failed! This command can only be ran inside of a ticket.")
        return True
    return app_commands.check(predicate)

def get_ticket_data():
    with open('Assets/tickets.json', 'r') as file:
        tickets = json.load(file)
        del tickets['TOGGLE_STATUS']
        return tickets 

def seconds_to_format(seconds):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if days:
        time_parts.append(f"{days}d")
    if hours:
        time_parts.append(f"{hours}h")
    if minutes:
        time_parts.append(f"{minutes}m")
    time_parts.append(f"{seconds}s")
    return " ".join(time_parts)

async def is_found(user: discord.Member, statistic: str):
    user_id: int = user.id
    rows = execute(f"SELECT {statistic} FROM statistics WHERE user_ID = '{user_id}'")
    if rows:
        return rows[0][statistic]
    else:
        await new_entry(user)
        return 0

async def new_entry(user: discord.Member):
    execute(f"INSERT INTO statistics (user_ID, tickets_closed, messages_sent, warnings, mutes, temp_bans, bans, screenshares, manual_bans, blacklists, revives, appeals, threads_locked, strike_team_votes, characters_sent, punishment_requests) VALUES ('{user.id}', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')")

def get_embed_logo_url(logo_path: Optional[str]) -> Optional[str]:
    if not logo_path:
        return None

    if logo_path.startswith(("http://", "https://")):
        return logo_path

    if os.path.isfile(logo_path):
        filename = os.path.basename(logo_path)
        return f"attachment://{filename}"

    return None