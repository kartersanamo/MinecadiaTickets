# Minecadia Tickets Bot

Discord bot for the Minecadia support ticket system.

## What it does

- Open, close, add, remove, move, and rename tickets
- Ticket blacklists, active ticket tracking, and ticket logs
- Ticket count voice channel and dashboard HTTP API
- Analytics for ticket commands

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add DISCORD_TOKEN, DB_*, TICKET_BLACKLIST_WEBHOOK
python main.py
```

## Config

- `.env` — token, database, webhook URL
- `assets/config.json` — guild, channels, role hierarchy, ticket categories
