import discord

from core.database import execute


async def is_found(user: discord.Member, statistic: str):
    user_id: int = user.id
    rows = execute(f"SELECT {statistic} FROM statistics WHERE user_ID = '{user_id}'")
    if rows:
        return rows[0][statistic]
    await new_entry(user)
    return 0


async def new_entry(user: discord.Member):
    execute(
        f"INSERT INTO statistics (user_ID, tickets_closed, messages_sent, warnings, mutes, temp_bans, bans, screenshares, manual_bans, blacklists, revives, appeals, threads_locked, strike_team_votes, characters_sent, punishment_requests) VALUES ('{user.id}', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0', '0')"
    )
