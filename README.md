
# Stories Bot

A Telegram bot that publishes stories (photos/videos) according to a schedule.

## Installation

```bash
pip install git+https://github.com/GeorgeFromGeorgea/stories_bot.git
```

Or after cloning:

```bash
pip install .
```

## Usage

First, obtain your Telegram API ID and Hash from https://my.telegram.org, and
a bot token from [@BotFather](https://t.me/BotFather).

Create a `.env` file (or set environment variables). See `.env.example`:

```dotenv
# Publisher (userbot, Telethon) — required
API_ID=your_api_id
API_HASH=your_api_hash

# Manager bot (python-telegram-bot) — required to run stories-manager
BOT_TOKEN=your_bot_token

# Optional
SESSION_NAME=stories_session  # default: stories_session
CHECK_INTERVAL=30             # seconds between checks (default: 30)
TIMEZONE=Europe/Moscow        # IANA timezone (default: Europe/Moscow)
DB_NAME=stories_bot.db        # SQLite path (default: stories_bot.db)
MEDIA_DIR=media               # media storage dir (default: media)
```

Credentials are read from the environment (and `.env` if `python-dotenv` is
installed). Nothing is hardcoded in the source.

Then run the publisher:

```bash
stories-bot
```

And, in a separate process, the manager bot used to upload media and schedule
posts:

```bash
stories-manager
```

The bot will create a SQLite database `stories_bot.db` in the current directory
and a session file.

## Configuration

All configuration is via environment variables (see the table above). Using a
`.env` file is recommended; never commit it.

## Media Management

Use the companion manager bot (`stories-manager`) to upload media to the pool
and schedule posts (now / daily / once) directly from Telegram. See
`stories_bot/manager_bot.py`.

## License

MIT
