# Stories Bot 📸

Telegram-бот для автоматической публикации Stories. Управляй публикациями через бота, а бот публикует от твоего имени по расписанию.

## 🚀 Возможности

- **📸 Загрузка медиа** — отправляй фото и видео прямо в бота
- **⏰ Планирование публикаций** — опубликовать сразу, по расписанию (разово) или ежедневно
- **🎲 Случайный выбор** — бот автоматически выбирает случайное фото/видео из пула
- **🚫 Уникальность** — одна и та же комбинация медиа+подпись не повторяется в один день
- **📱 Управление через Telegram** — удобное меню с кнопками
- **🔄 Автопубликация** — публикация от твоего имени через userbot
- **📊 Статистика** — отслеживание опубликованных постов

## 📋 Требования

- Python 3.9+
- Telegram аккаунт
- Токен бота от @BotFather
- API_ID и API_HASH от [my.telegram.org/apps](https://my.telegram.org/apps)

## ⚙️ Установка

### Linux / macOS

```bash
pip install git+https://github.com/GeorgeFromGeorgea/stories_bot.git
```

### Windows

**1. Установи Python** (если ещё не установлен):

```powershell
winget install Python.Python.3.12
```

> После установки **закрой и открой PowerShell заново**.

**2. Проверь, что Python работает:**

```powershell
python --version
```

Должно показать `Python 3.12.x`.

**3. Установи Git** (если ещё не установлен):

```powershell
winget install Git.Git
```

> После установки **закрой и открой PowerShell заново**.

**4. Установи бота:**

```powershell
python -m pip install -U git+https://github.com/GeorgeFromGeorgea/stories_bot.git
```

> Если `python --version` показывает просто "Python" (без версии) — значит это заглушка Microsoft Store. Удали её и установи Python через `winget` или с [python.org](https://www.python.org/downloads/), обязательно отметив **"Add Python to PATH"**.

## 🔧 Настройка

### 1. Инициализация конфигурации

```bash
stories-bot init
```

Мастер настройки спросит:
- **BOT_TOKEN** — получи у [@BotFather](https://t.me/BotFather)
- **API_ID** — получи на [my.telegram.org/apps](https://my.telegram.org/apps)
- **API_HASH** — получи на [my.telegram.org/apps](https://my.telegram.org/apps)
- **SESSION_NAME** — имя сессии (можно оставить по умолчанию)

### 2. Первый вход (userbot)

```bash
stories-bot login
```

Введи номер телефона и код подтверждения. Это нужно только один раз — для авторизации userbot (публикатора).

### 3. Запуск бота

```bash
stories-bot run
```

## 📖 CLI команды

| Команда | Описание |
|---------|----------|
| `stories-bot init` | Интерактивный мастер настройки |
| `stories-bot set-token` | Установить токен бота |
| `stories-bot set-api-id` | Установить API_ID |
| `stories-bot set-api-hash` | Установить API_HASH |
| `stories-bot config` | Показать текущую конфигурацию |
| `stories-bot login` | Первый вход userbot |
| `stories-bot run` | Запуск бота (менеджер + публикатор) |
| `stories-bot help` | Показать справку |

### Быстрая настройка через терминал

```bash
# Установить токен бота (получи у @BotFather)
stories-bot set-token "YOUR_BOT_TOKEN_HERE"

# Установить API_ID (получи на my.telegram.org/apps)
stories-bot set-api-id YOUR_API_ID

# Установить API_HASH (получи на my.telegram.org/apps)
stories-bot set-api-hash "YOUR_API_HASH_HERE"

# Посмотреть текущие настройки
stories-bot config

# Первый вход (после установки всех ключей)
stories-bot login

# Запуск бота
stories-bot run
```

## 🤖 Команды бота в Telegram

> ⚠️ **При первом запуске обязательно введи `/start`** — без этого кнопки меню не появятся.

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню |
| `/list` | Список запланированных постов |
| `/add_media` | Добавить медиа в пул |
| `/media_pool` | Просмотр пула медиа |
| `/delete_media ID` | Удалить медиа из пула |
| `/stats` | Статистика публикаций |
| `/cancel` | Отмена текущего действия |

## 🎛 Кнопки меню

| Кнопка | Описание |
|--------|----------|
| 🚀 Старт | Главное меню |
| 📋 Отложенные | Просмотр запланированных постов |
| 📥 Добавить медиа | Загрузить фото/видео в пул |
| 📦 Пул медиа | Все загруженные медиафайлы |
| 📊 Статистика | Статистика публикаций |
| 🗑 Сброс | Сброс текущего состояния |
| 🗓 Планировать публикацию | Создать запланированный пост |
| 🔗 Подпись репостера | Настройка дефолтной подписи |
| 🕐 Ежедневные | Настройка ежедневных публикаций |
| 🔄 Рестарт | Перезапуск бота |

## 🔄 Как работает

1. **Загрузи медиа** — отправь фото или видео боту
2. **Создай пост** — выбери когда публиковать:
   - **Сразу** — публикация немедленно
   - **Ежедневно** — автоматическая публикация каждый день в указанное время
   - **Разово** — публикация в указанную дату и время
3. **Автопубликация** — бот опубликует автоматически

## 📁 Пул медиа

Бот хранит медиафайлы в пуле. Для ежедневных публикаций:
- Каждый день выбирается случайное медиа
- Одно и то же медиа не повторяется в один день
- Разные подписи имеют независимые пулы

## 🔐 Конфигурация (.env файл)

Создай файл `.env` в рабочей директории:

```env
BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
API_ID=YOUR_API_ID
API_HASH="YOUR_API_HASH_HERE"
SESSION_NAME="stories_session"
```

## 🖥 Размещение на сервере (systemd)

### 1. Создай сервисные файлы

**publisher.service:**
```ini
[Unit]
Description=Stories Bot - Publisher (Telethon)
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/stories_bot_pkg
ExecStart=/usr/bin/python3 -m stories_bot.publisher
Restart=always
RestartSec=10
User=root
Environment=PYTHONPATH=/root/stories_bot_pkg

[Install]
WantedBy=multi-user.target
```

**manager.service:**
```ini
[Unit]
Description=Stories Bot - Manager (Telegram Bot API)
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/stories_bot_pkg
ExecStart=/usr/bin/python3 -m stories_bot.manager
Restart=always
RestartSec=10
User=root
Environment=PYTHONPATH=/root/stories_bot_pkg

[Install]
WantedBy=multi-user.target
```

### 2. Запусти сервисы

```bash
# Скопируй файлы
sudo cp publisher.service manager.service /etc/systemd/system/

# Перезагрузи systemd
sudo systemctl daemon-reload

# Запусти
sudo systemctl start stories-publisher stories-manager

# Включи автозапуск
sudo systemctl enable stories-publisher stories-manager

# Проверь статус
sudo systemctl status stories-publisher stories-manager
```

### 3. Логи

```bash
# Смотреть логи в реальном времени
sudo journalctl -u stories-publisher -f
sudo journalctl -u stories-manager -f

# Последние 50 строк
sudo journalctl -u stories-publisher -n 50
```

## 🔄 Обновление

### Linux / macOS

```bash
pip install -U git+https://github.com/GeorgeFromGeorgea/stories_bot.git

# Перезапусти сервисы (если используешь systemd)
sudo systemctl restart stories-publisher stories-manager
```

### Windows

```powershell
python -m pip install -U git+https://github.com/GeorgeFromGeorgea/stories_bot.git
```

> Флаг `-U` (--upgrade) обновляет пакет на месте. Переустанавливать не нужно.

## 🔍 Решение проблем

### Бот не отвечает

```bash
# Проверь, запущен ли бот
ps aux | grep stories-bot

# Проверь логи
journalctl -u stories-bot -f
```

### Ошибка входа

```bash
# Удали файл сессии и попробуй снова
rm *.session
stories-bot login
```

### Ошибки токена

Убедись, что в файле `.env` правильный токен от @BotFather.

### Бот не публикует Stories

Проверь, что userbot авторизован:
```bash
stories-bot login
```

## 📄 Лицензия

MIT
