# ContentForwardBot

Telegram content management and forwarding bot.

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python main.py`

## Structure

- `main.py` - Entry point
- `config.py` - Settings and env loading
- `bot/` - Telegram bot handlers and keyboards
- `core/` - Database, queue, and pyrogram client
- `utils/` - Logger and helpers
