
# Stories Bot

A Telegram bot that publishes stories (photos/videos) according to a schedule.

## Installation

```bash
pip install git+https://github.com/yourusername/stories-bot.git
```

Or after cloning:

```bash
pip install .
```

## Usage

First, obtain your Telegram API ID and Hash from https://my.telegram.org.

Create a `.env` file (or set environment variables):

```dotenv
API_ID=your_api_id
API_HASH=your_api_hash
SESSION_NAME=stories_session  # optional, default: stories_session
CHECK_INTERVAL=30             # optional, seconds between checks
```

Then run:

```bash
stories-bot
```

The bot will create a SQLite database `stories_bot.db` in the current directory and a session file.

## Configuration

You can also edit the constants in `stories_bot/stories_bot.py` directly, but using environment variables is recommended.

## Media Management

Use the companion manager bot (or direct database inserts) to add media and schedule posts.

See `manager_bot.py` for a simple CLI to add media and posts.

## License

MIT
