# Stories Bot

Telegram Stories publisher bot with scheduling support.

## Features

- 📸 Upload photos/videos to media pool
- ⏰ Schedule posts (one-time or daily)
- 🎲 Random media selection with daily uniqueness
- 📱 Interactive management via Telegram bot
- 🔄 Auto-publishing via userbot

## Installation

### From GitHub (recommended)

```bash
pip install git+https://github.com/yourusername/stories-bot.git
```

### From source

```bash
git clone https://github.com/yourusername/stories-bot.git
cd stories-bot
pip install .
```

## Setup

### 1. Initialize configuration

```bash
stories-bot init
```

This will ask you for:
- **BOT_TOKEN** - Get from [@BotFather](https://t.me/BotFather)
- **API_ID** - Get from [my.telegram.org/apps](https://my.telegram.org/apps)
- **API_HASH** - Get from [my.telegram.org/apps](https://my.telegram.org/apps)

### 2. First-time login (userbot)

```bash
stories-bot login
```

Enter your phone number and verification code when prompted.

### 3. Run the bot

```bash
stories-bot run
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `stories-bot init` | Interactive setup wizard |
| `stories-bot login` | First-time userbot login |
| `stories-bot run` | Start the bot |
| `stories-bot help` | Show help |

## Configuration (.env file)

Create a `.env` file in your working directory:

```env
BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
API_ID=12345678
API_HASH="0123456789abcdef0123456789abcdef"
SESSION_NAME="stories_session"
```

## Usage

### Manager Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show main menu |
| `/list` | List scheduled posts |
| `/daily_list` | List daily posts |
| `/add_media` | Add media to pool |
| `/media_pool` | View media pool |
| `/stats` | Show statistics |
| `/cancel` | Cancel current operation |

### Menu Buttons

- 🚀 Старт - Main menu
- 📋 Отложенные - View scheduled posts
- 📊 Статистика - Statistics
- 📥 Добавить медиа - Add media to pool
- 📦 Пул медиа - View media pool
- 🗑 Сброс - Reset
- 🔄 Рестарт - Restart bot
- 🕐 Ежедневные - Schedule daily post

## Updating

To update to the latest version from GitHub:

```bash
# Update the package
pip install -U git+https://github.com/GeorgeFromGeorgea/stories_bot.git

# Restart the bot services (if using systemd)
systemctl restart stories-publisher.service
systemctl restart stories-manager.service
```

> **Note:** The `-U` (--upgrade) flag updates the package in-place. No need to uninstall first.

## How it works

1. **Upload media** - Send photos/videos to the bot
2. **Create post** - Choose when to publish (now/daily/one-time)
3. **Auto-publish** - Bot publishes automatically at scheduled time

## Media Pool

The bot maintains a pool of media files. For daily posts:
- Random media is selected each day
- Same media won't repeat on the same day
- Different captions have independent pools

## Troubleshooting

### Bot not responding

```bash
# Check if bot is running
ps aux | grep stories-bot

# Check logs
journalctl -u stories-bot -f
```

### Login failed

```bash
# Delete session file and try again
rm *.session
stories-bot login
```

### Token errors

Make sure your `.env` file has the correct token from @BotFather.

## License

MIT
