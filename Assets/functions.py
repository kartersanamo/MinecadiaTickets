from discord import app_commands
import mysql.connector
import discord
import logger
import json
import time

# Variables that represent loggers that can be accessed anywhere in the bot's code simply by importing the logger
# Then you can run i.e `log_tasks.info("...")` to log information under the logger of "Tasks"
log_tasks = logger.logging.getLogger("Tasks")
log_commands = logger.logging.getLogger("Commands")

# Connection pool global variable
pool = None

def get_data() -> dict:
    """
    Loads the configuration data from a JSON file.

    This function reads the contents of the "MinecadiaTickets/Assets/config.json" file and
    parses it as a JSON object. The parsed JSON object is then returned.

    Parameters:
    None

    Returns:
    dict: A dictionary containing the configuration data from the JSON file.

    Raises:
    FileNotFoundError: If the specified file does not exist.
    json.JSONDecodeError: If the specified file contains invalid JSON data.
    """
    with open("MinecadiaTickets/Assets/config.json", "r") as file:
        return json.load(file)
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
    """
    Executes a given SQL query on the MySQL database and returns the result.

    This function checks if the connection pool exists. If not, it initializes the pool first.
    It then acquires a connection from the pool, executes the SQL query, and fetches the results.

    Parameters:
    - query (str): The SQL query to be executed.

    Returns:
    - list: A list of dictionaries, where each dictionary represents a row returned by the query.

    Raises:
    - Exception: If any error occurs during the connection process or query execution.

    This function is an asynchronous function and should be awaited when called.
    """
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
    """
    A decorator function that measures the execution time of a given function and logs the results.

    Parameters:
    - action_name (str): The name of the action being performed by the decorated function.
    - log (bool, optional): A flag indicating whether to log the execution time. Defaults to None.

    Returns:
    - A decorator function that wraps the input function and logs the execution time.

    The decorator function logs the start time of the decorated function, executes it, measures the execution time,
    and logs the result (success or failure) along with the execution time. If the execution time exceeds 2 seconds,
    a warning message is logged.
    """
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
    """
    A decorator function that checks if a Discord interaction is taking place in a ticket channel.

    This function is designed to be used as a decorator for Discord interaction commands. It raises a
    CheckFailure if the interaction is not taking place in a ticket channel.

    Returns:
    - A decorator function that wraps the input function and checks if the interaction is in a ticket channel.

    Raises:
    - app_commands.CheckFailure: If the interaction is not taking place in a ticket channel.

    Example:
    ```python
    @app_commands.command()
    @is_ticket()
    async def close_ticket(self, interaction: discord.Interaction):
        # Code to close the ticket
        pass
    ```
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.channel.category or interaction.channel.category.id not in data['TICKET_CATEGORIES']:
            raise app_commands.CheckFailure("`❌` Failed! This command can only be ran inside of a ticket.")
        return True
    return app_commands.check(predicate)

def get_ticket_data():
    with open('MinecadiaTickets/Assets/tickets.json', 'r') as file:
        tickets = json.load(file)
        del tickets['TOGGLE_STATUS']
        return tickets 

def seconds_to_format(seconds):
    """
    Converts seconds (usually in difference of unix) to a formatted string of days, hours, minutes, and seconds.

    Parameters:
    seconds (int): The number of seconds to be converted.

    Returns:
    str: A formatted string representing the input seconds in the format "Xd Yh Zm Ws", where X, Y, Z, and W are the number of days, hours, minutes, and seconds respectively.
    """
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
    """
    Checks if a user (presumably a staff member) exists in the statistics database.
    If they do not exist, add them to it.
    This function will always return the statistic. If they aren't found, then it will return 0 since it's their first of that statistic.

    Parameters:
    - user (discord.Member): The Discord member for whom the statistic is being checked.
    - statistic (str): The name of the statistic to retrieve.

    Returns:
    - int: The value of the specified statistic for the given user. If the user does not exist, returns 0.
    """
    user_id: int = user.id
    rows = execute(f"SELECT {statistic} FROM statistics WHERE user_ID = '{user_id}'")
    if rows:
        return rows[0][statistic]
    else:
        await new_entry(user)
        return 0

async def new_entry(user: discord.Member):
    """
    Adds a new user to the statistics database.
    This function should never be called on its own, but instead only called from the 'is_found' function.

    Parameters:
    - user (discord.Member): The Discord member for whom a new entry is being created in the statistics database.

    Returns:
    - None: This function does not return any value. It only executes an SQL INSERT query to add a new entry in the statistics database.
    """
    execute(f"INSERT INTO statistics (user_ID, tickets_closed, messages_sent, warnings, mutes, temp_bans, bans, screenshares, manual_bans, blacklists, revives, appeals, threads_locked, strike_team_votes, characters_sent, punishment_requests) VALUES ('{user.id}', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')")