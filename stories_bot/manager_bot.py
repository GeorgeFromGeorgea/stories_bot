#!/usr/bin/env python3
"""
Management Bot - Управляющий бот для Telegram Stories.
Полная версия: добавление, просмотр, редактирование и удаление постов.
"""
import logging
import os
from pathlib import Path
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackContext, filters, ConversationHandler, CallbackQueryHandler
)
from telegram.constants import ParseMode  # kept for compatibility

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv опционален

# Поддержка запуска и как пакета (python -m stories_bot.manager_bot),
# и как отдельного скрипта (python manager_bot.py).
try:
    from . import stories_db
except ImportError:
    import stories_db

# --- Конфигурация (через переменные окружения / .env) ---
# Токен получи у @BotFather.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MEDIA_DIR = os.environ.get("MEDIA_DIR", "media")
# --------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния для диалога добавления (range гарантирует уникальность всех стейтов)
(
    CAPTION,
    CHOOSE_PLAN,
    PICK_HOUR,
    PICK_MINUTE,
    PICK_CALENDAR,
    SCHEDULE_DAILY_HOUR,
    SCHEDULE_DAILY_MINUTE,
    EDIT_FIELD,
    EDIT_VALUE,
    CONFIRM_DELETE,
    EDIT_MEDIA,
    ADD_MEDIA_WAIT,
) = range(12)

# Хранилище данных пользователя (временное)
user_data = {}

Path(MEDIA_DIR).mkdir(exist_ok=True)

# ========== ПОСТРОИТЕЛИ КЛАВИАТУР ВРЕМЕНИ ==========

def build_hour_picker(prefix: str) -> InlineKeyboardMarkup:
    """Пикер часов 00-23, prefix = 'daily' или 'once'"""
    buttons = []
    row = []
    for h in range(24):
        row.append(InlineKeyboardButton(f"{h:02d}", callback_data=f"{prefix}_hour_{h:02d}"))
        if len(row) == 6:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

def build_minute_picker(prefix: str, hour: str) -> InlineKeyboardMarkup:
    """Пикер минут :00/:15/:30/:45"""
    buttons = []
    for m in [0, 15, 30, 45]:
        buttons.append([InlineKeyboardButton(f":{m:02d}", callback_data=f"{prefix}_min_{hour}_{m:02d}")])
    buttons.append([InlineKeyboardButton("◀ Назад к часам", callback_data=f"{prefix}_back_hour")])
    return InlineKeyboardMarkup(buttons)

def build_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    """Inline-календарь для выбора даты"""
    import calendar
    from datetime import date
    
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    month_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    buttons = []
    
    # Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    buttons.append([
        InlineKeyboardButton("◀", callback_data=f"cal_prev_{prev_year}_{prev_month:02d}"),
        InlineKeyboardButton(f"{month_names[month-1]} {year}", callback_data="cal_ignore"),
        InlineKeyboardButton("▶", callback_data=f"cal_next_{next_year}_{next_month:02d}"),
    ])
    
    # Дни недели
    buttons.append([InlineKeyboardButton(d, callback_data="cal_ignore") for d in day_names])
    
    # Дни месяца
    today = date.today()
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_ignore"))
            else:
                d = date(year, month, day)
                if d < today:
                    row.append(InlineKeyboardButton("✗", callback_data="cal_ignore"))
                elif d == today:
                    row.append(InlineKeyboardButton(f"·{day}·", callback_data=f"cal_day_{year}_{month:02d}_{day:02d}"))
                else:
                    row.append(InlineKeyboardButton(str(day), callback_data=f"cal_day_{year}_{month:02d}_{day:02d}"))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton("◀ Отмена", callback_data="cal_cancel")])
    return InlineKeyboardMarkup(buttons)

# ========== БЛОК ДОБАВЛЕНИЯ ПОСТА ==========

async def start(update: Update, context: CallbackContext):
    # Создаем клавиатуру снизу (Reply Keyboard) с русскими названиями
    keyboard = [
        ["🚀 Старт", "📋 Отложенные"],
        ["📥 Добавить медиа", "📦 Пул медиа"],
        ["📊 Статистика", "🗑 Сброс"],
        ["🗓 Планировать публикацию"],
        ["🕐 Ежедневные", "🔄 Рестарт"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🤖 Управляющий бот для Telegram Stories\n\n"
        "Просто отправь мне фото или видео, и я помогу запланировать историю!\n\n"
        "Доступные команды:\n"
        "/start — перезапустить бота и показать меню\n"
        "/add_media — добавить фото/видео в пул для рандомной публикации\n"
        "/media_pool — показать все медиа в пуле\n"
        "/delete_media ID — удалить медиа из пула\n"
        "/list — список запланированных постов\n"
        "/stats — статистика\n"
        "/cancel — отмена действия",
        reply_markup=reply_markup
    )

async def handle_media(update: Update, context: CallbackContext):
    """Принимаем медиа от пользователя."""
    user_id = update.effective_user.id
    
    if not (update.message.photo or update.message.video):
        await update.message.reply_text("❌ Отправь фото или видео!")
        return ConversationHandler.END

    # Скачиваем файл
    file_id = None
    media_type = "unknown"
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        media_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "video"
    
    new_file = await context.bot.get_file(file_id)
    ext = ".jpg" if media_type == "photo" else ".mp4"
    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{new_file.file_unique_id}{ext}"
    file_path = str(Path(MEDIA_DIR) / file_name)
    
    await new_file.download_to_drive(file_path)
    logger.info(f"✅ Медиа сохранено: {file_path}")
    
    # Сохраняем в БД медиа
    media_id = stories_db.add_media(
        file_path=file_path,
        file_name=file_name,
        media_type=media_type,
        caption=update.message.caption
    )
    
    # Запоминаем состояние
    user_data[user_id] = {'media_id': media_id, 'media_type': media_type}
    
    # Спрашиваем про текст
    await update.message.reply_text(
        "✏️ Введите текст (подпись) для истории (или отправьте '-' если без текста):"
    )
    return CAPTION

async def get_caption(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    caption = update.message.text
    
    if caption == '-':
        caption = ""
        
    user_data[user_id]['caption'] = caption
    
    # Предлагаем выбрать план
    buttons = [
        [InlineKeyboardButton("⏰ Опубликовать сейчас", callback_data="plan_now")],
        [InlineKeyboardButton("🔄 Ежедневно", callback_data="plan_daily")],
        [InlineKeyboardButton("📅 Один раз", callback_data="plan_once")],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "✅ Текст принят! Что делаем дальше?",
        reply_markup=reply_markup
    )
    return CHOOSE_PLAN

async def button_handler_add(update: Update, context: CallbackContext):
    """Обработка кнопок при выборе типа публикации."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    ud = user_data[user_id]
    
    if data == "plan_now":
        # Опубликовать сейчас
        media_id = ud['media_id']
        caption = ud['caption']
        post_id = stories_db.add_post(post_type="now", post_time="now", media_id=media_id, caption=caption)
        await query.edit_message_text(f"✅ История #{post_id} поставлена в очередь на публикацию!")
        return ConversationHandler.END
        
    elif data == "plan_daily":
        # Сохраняем флаг, что это ежедневный пост
        ud['is_daily'] = True
        await query.edit_message_text(
            "⏰ Выберите час публикации:",
            reply_markup=build_hour_picker("daily")
        )
        return PICK_HOUR
        
    elif data == "plan_once":
        ud['is_daily'] = False
        now = datetime.now()
        await query.edit_message_text(
            "📅 Выберите дату:",
            reply_markup=build_calendar(now.year, now.month)
        )
        return PICK_CALENDAR


async def button_handler_time(update: Update, context: CallbackContext):
    """Обработка выбора времени через inline-пикеры."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    ud = user_data.get(user_id, {})
    
    # --- ЕЖЕДНЕВНО: выбор часа ---
    if data.startswith("daily_hour_"):
        hour = data.replace("daily_hour_", "")
        ud['picked_hour'] = hour
        await query.edit_message_text(
            f"⏰ Выберите минуты (час: {hour}):",
            reply_markup=build_minute_picker("daily", hour)
        )
        return PICK_MINUTE
    
    # --- ЕЖЕДНЕВНО: выбор минут ---
    elif data.startswith("daily_min_"):
        # daily_min_09_00
        parts = data.replace("daily_min_", "").split("_")
        hour, minute = parts[0], parts[1]
        time_str = f"{hour}:{minute}"
        
        media_id = -1  # Специальное значение: брать случайное медиа из пула
        caption = ud['caption']
        post_id = stories_db.add_post(post_type="daily", post_time=time_str, media_id=media_id, caption=caption)
        await query.edit_message_text(f"✅ Ежедневная публикация #{post_id} запланирована на {time_str}!\nМедиа будет выбрано случайно из пула.")
        return ConversationHandler.END
    
    # --- ЕЖЕДНЕВНО: назад к часам ---
    elif data == "daily_back_hour":
        await query.edit_message_text(
            "⏰ Выберите час публикации:",
            reply_markup=build_hour_picker("daily")
        )
        return PICK_HOUR
    
    # --- РАЗОВОЙ: выбор часа ---
    elif data.startswith("once_hour_"):
        hour = data.replace("once_hour_", "")
        ud['picked_hour'] = hour
        await query.edit_message_text(
            f"⏰ Выберите минуты (час: {hour}):",
            reply_markup=build_minute_picker("once", hour)
        )
        return PICK_MINUTE
    
    # --- РАЗОВОЙ: выбор минут ---
    elif data.startswith("once_min_"):
        parts = data.replace("once_min_", "").split("_")
        hour, minute = parts[0], parts[1]
        date_str = ud['picked_date']
        datetime_str = f"{date_str} {hour}:{minute}"
        
        media_id = ud['media_id']
        caption = ud['caption']
        post_id = stories_db.add_post(post_type="once", post_time=datetime_str, media_id=media_id, caption=caption)
        await query.edit_message_text(f"✅ Разовая публикация #{post_id} запланирована на {datetime_str}!")
        return ConversationHandler.END
    
    # --- РАЗОВОЙ: назад к часам ---
    elif data == "once_back_hour":
        await query.edit_message_text(
            f"📅 {ud.get('picked_date', '?')} — выберите час:",
            reply_markup=build_hour_picker("once")
        )
        return PICK_HOUR
    
    # --- РАЗОВОЙ: навигация календаря ---
    elif data.startswith("cal_prev_") or data.startswith("cal_next_"):
        parts = data.split("_")
        year, month = int(parts[2]), int(parts[3])
        await query.edit_message_text(
            "📅 Выберите дату:",
            reply_markup=build_calendar(year, month)
        )
        return PICK_CALENDAR
    
    # --- РАЗОВОЙ: выбор дня ---
    elif data.startswith("cal_day_"):
        parts = data.replace("cal_day_", "").split("_")
        year, month, day = parts[0], parts[1], parts[2]
        ud['picked_date'] = f"{year}-{month}-{day}"
        await query.edit_message_text(
            f"📅 {year}-{month}-{day} — выберите час:",
            reply_markup=build_hour_picker("once")
        )
        return PICK_HOUR
    
    # --- ОТМЕНА КАЛЕНДАРЯ ---
    elif data == "cal_cancel":
        await query.edit_message_text("❌ Создание поста отменено.")
        return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    await update.message.reply_text("❌ Действие отменено.")
    return ConversationHandler.END

async def restart_bot(update: Update, context: CallbackContext):
    """Перезапуск бота через /restart команду"""
    await update.message.reply_text("🔄 Перезапускаю бота...")
    
    # Останавливаем текущий процесс
    import os
    import sys
    # Отправляем сигнал завершения текущему процессу
    os._exit(0)
    # Альтернативный вариант: перезапуск через exec
    # os.execv(sys.executable, ['python'] + sys.argv)

# ========== БЛОК ПРОСМОТРА, РЕДАКТИРОВАНИЯ, УДАЛЕНИЯ ==========

async def cmd_list(update: Update, context: CallbackContext):
    """Команда /list — показать активные посты."""
    user_id = update.effective_user.id
    # Сбрасываем состояние диалога, если было
    if user_id in user_data:
        del user_data[user_id]
    
    posts = stories_db.get_active_posts()
    if not posts:
        await update.message.reply_text("📭 Активных постов нет.")
        return
    
    await update.message.reply_text(f"📸 Найдено {len(posts)} активных постов:")
    
    for p in posts:
        caption = p['caption'] or 'нет'
        buttons = [
            [InlineKeyboardButton("📝 Редактировать", callback_data=f"edit_{p['id']}"),
             InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{p['id']}")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        # media_id == -1: медиа выбирается случайно из пула в момент публикации
        if p['media_id'] == -1:
            await update.message.reply_text(
                f"🔹 *Пост #{p['id']}*\n"
                f"Тип: {p['post_type']}\n"
                f"Время: {p['post_time']}\n"
                f"Медиа: случайно из пула\n"
                f"Подпись: {caption[:100]}",
                reply_markup=reply_markup,
            )
            continue

        media_info = stories_db.get_media(p['media_id'])
        if not media_info:
            await update.message.reply_text(
                f"🔹 *Пост #{p['id']}* - медиа не найдено",
                reply_markup=reply_markup,
            )
            continue
            
        media_type = media_info['media_type']
        file_path = media_info['file_path']

        # Формируем описание поста
        post_caption = (
            f"🔹 *Пост #{p['id']}*\n"
            f"Тип: {p['post_type']}\n"
            f"Время: {p['post_time']}\n"
            f"Подпись: {caption[:100]}"
        )

        # Отправляем медиа
        try:
            if media_type == "photo":
                with open(file_path, 'rb') as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption=post_caption,
                        reply_markup=reply_markup,
                        
                    )
            elif media_type == "video":
                with open(file_path, 'rb') as f:
                    await update.message.reply_video(
                        video=f,
                        caption=post_caption,
                        reply_markup=reply_markup,
                        
                    )
        except Exception as e:
            logger.error(f"Ошибка отправки медиа для поста #{p['id']}: {e}")
            await update.message.reply_text(
                f"🔹 *Пост #{p['id']}* - ошибка отображения медиа",
                reply_markup=reply_markup,
                
            )

async def cmd_daily_list(update: Update, context: CallbackContext):
    """Команда /daily_list — показать все ежедневные посты с кнопками удаления."""
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]

    posts = stories_db.get_daily_posts()
    if not posts:
        await update.message.reply_text("📭 Ежедневных постов нет.")
        return

    for p in posts:
        media_info = ""
        if p['media_id'] == -1:
            media_info = "🎲 случайное из пула"
        elif p.get('file_name'):
            media_info = f"📎 {p['file_name']}"
        else:
            media_info = "📎 медиа не найдено"

        caption = (p['caption'] or 'нет')[:60]

        buttons = [[
            InlineKeyboardButton("🗑 Удалить", callback_data=f"del_daily_{p['id']}")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.message.reply_text(
            f"🔹 Пост #{p['id']}\n"
            f"   Время: {p['post_time']}\n"
            f"   Медиа: {media_info}\n"
            f"   Подпись: {caption}",
            reply_markup=reply_markup
        )

async def button_handler_delete_daily(update: Update, context: CallbackContext):
    """Обработка удаления ежедневного поста."""
    query = update.callback_query
    await query.answer()
    data = query.data

    post_id = int(data.replace("del_daily_", ""))
    post = stories_db.get_post_by_id(post_id)

    if not post:
        await query.edit_message_text(f"❌ Пост #{post_id} не найден.")
        return

    stories_db.deactivate_post(post_id)

    await query.edit_message_text(
        f"🗑 Пост #{post_id} (время: {post['post_time']}) удалён.\n"
        f"Публикация в это время больше не будет происходить."
    )

async def button_handler_edit(update: Update, context: CallbackContext):
    """Обработка кнопок редактирования и удаления."""
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"🔵 Получен callback: {data}")
    
    user_id = query.from_user.id
    
    # --- Редактирование: выбор поста ---
    if data.startswith("edit_"):
        post_id = int(data.split("_")[1])
        post = None
        posts = stories_db.get_active_posts()
        for p in posts:
            if p['id'] == post_id:
                post = p
                break
        
        if not post:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Пост не найден."
            )
            return ConversationHandler.END
            
        user_data[user_id] = {'post_id': post_id}
        
        buttons = [
            [InlineKeyboardButton("Тип (now/daily/once)", callback_data=f"field_{post_id}_type")],
            [InlineKeyboardButton("Время", callback_data=f"field_{post_id}_time")],
            [InlineKeyboardButton("Подпись", callback_data=f"field_{post_id}_caption")],
            [InlineKeyboardButton("📷 Медиа", callback_data=f"field_{post_id}_media")],
            [InlineKeyboardButton("❌ Отмена", callback_data="edit_cancel")]
        ]
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"📝 Редактирование поста #{post_id}\n"
                f"Текущий тип: {post['post_type']}\n"
                f"Текущее время: {post['post_time']}\n"
                f"Текущая подпись: {(post['caption'] or 'нет')[:30]}...\n\n"
                f"Что хотите изменить?"
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return EDIT_FIELD

    # --- Выбор поля для редактирования ---
    elif data.startswith("field_"):
        parts = data.split("_")
        post_id = int(parts[1])
        field = parts[2]
        
        user_data[user_id] = {'post_id': post_id, 'field': field}
        
        if field == 'media':
            await query.edit_message_text("📷 Пришлите новое фото или видео для этого поста:")
            return EDIT_MEDIA
        
        field_names = {'type': 'тип', 'time': 'время', 'caption': 'подпись'}
        await query.edit_message_text(f"✏️ Введите новое значение для поля '{field_names.get(field, field)}':")
        return EDIT_VALUE

    # --- Удаление: запрос подтверждения ---
    elif data.startswith("delete_"):
        post_id = int(data.split("_")[1])
        user_data[user_id] = {'post_id': post_id}
        
        buttons = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_del_{post_id}")],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data="del_cancel")]
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🗑 Вы уверены, что хотите удалить пост #{post_id}?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return CONFIRM_DELETE

    # --- Подтверждение удаления ---
    elif data.startswith("confirm_del_"):
        post_id = int(data.split("_")[2])
        success = stories_db.deactivate_post(post_id)
        if success:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ Пост #{post_id} удален из расписания."
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ Ошибка удаления поста #{post_id}."
            )
        return ConversationHandler.END
    
    # --- Отмена ---
    elif data in ["edit_cancel", "del_cancel"]:
        if user_id in user_data:
            del user_data[user_id]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Действие отменено."
        )
        return ConversationHandler.END

async def edit_value_input(update: Update, context: CallbackContext):
    """Принимаем новое значение для поля."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Сессия устарела. Начните заново с /list")
        return ConversationHandler.END
        
    state = user_data[user_id]
    post_id = state['post_id']
    field = state['field']
    
    update_data = {}
    if field == 'type':
        if text not in ['now', 'daily', 'once']:
            await update.message.reply_text("❌ Тип должен быть: now, daily или once")
            return EDIT_VALUE
        update_data['post_type'] = text
    elif field == 'time':
        update_data['post_time'] = text
    elif field == 'caption':
        update_data['caption'] = text
        
    success = stories_db.update_post(post_id, **update_data)
    if success:
        await update.message.reply_text(f"✅ Пост #{post_id} обновлен! Поле '{field}' изменено.")
    else:
        await update.message.reply_text(f"❌ Ошибка обновления поста #{post_id}.")
    
    del user_data[user_id]
    return ConversationHandler.END

async def edit_media_input(update: Update, context: CallbackContext):
    """Обработка нового медиа для редактируемого поста."""
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Сессия устарела. Начните заново с /list")
        return ConversationHandler.END
        
    state = user_data[user_id]
    post_id = state['post_id']
    
    # Получаем старый пост, чтобы удалить старый файл позже
    old_post = stories_db.get_post_by_id(post_id)
    if not old_post:
        await update.message.reply_text(f"❌ Пост #{post_id} не найден.")
        return ConversationHandler.END
        
    old_file = old_post.get('file_path')
    media_id = old_post.get('media_id')
    
    # Определяем тип и скачиваем файл
    media_type = None
    file_obj = None
    
    if update.message.photo:
        media_type = 'photo'
        file_obj = update.message.photo[-1]
    elif update.message.video:
        media_type = 'video'
        file_obj = update.message.video
    else:
        await update.message.reply_text("❌ Отправьте фото или видео.")
        return EDIT_MEDIA
        
    # Скачиваем файл
    file = await context.bot.get_file(file_obj.file_id)
    ext = 'jpg' if media_type == 'photo' else 'mp4'
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{MEDIA_DIR}/{timestamp}_post_{post_id}.{ext}"
    
    await file.download_to_drive(filename)
    await update.message.reply_text(f"✅ Медиа сохранено: {filename}")
    
    # Обновляем базу данных (таблица media)
    if media_id:
        success = stories_db.update_media(media_id, filename, media_type)
    else:
        # Если media_id нет (не должно случиться, но на всякий случай)
        await update.message.reply_text("❌ Ошибка: не найден media_id для поста.")
        return ConversationHandler.END
    
    if success:
        # Удаляем старый файл, если он есть и отличается
        if old_file and old_file != filename and os.path.exists(old_file):
            try:
                os.remove(old_file)
                await update.message.reply_text(f"🗑 Старый файл удален.")
            except Exception as e:
                logger.error(f"Ошибка удаления старого файла {old_file}: {e}")
        await update.message.reply_text(f"✅ Пост #{post_id} обновлен! Новое медиа установлено.")
    else:
        await update.message.reply_text(f"❌ Ошибка обновления медиа для поста #{post_id}.")
    
    del user_data[user_id]
    return ConversationHandler.END

async def cmd_stats(update: Update, context: CallbackContext):
    """Команда /stats"""
    user_id = update.effective_user.id
    # Сбрасываем состояние диалога, если было
    if user_id in user_data:
        del user_data[user_id]
    
    stats = stories_db.get_stats()
    await update.message.reply_text(
        "📊 Статистика публикаций:\n\n"
        f"Всего попыток: {stats['total']}\n"
        f"Успешно: {stats['success']}\n"
        f"Ошибок: {stats['failed']}"
    )

async def handle_menu_buttons(update: Update, context: CallbackContext):
    """Обработка нажатий кнопок меню (reply keyboard)."""
    text = update.message.text
    user_id = update.effective_user.id
    logger.info(f"handle_menu_buttons called for user {user_id}, text: {text}")
    
    # СБРОС ВСЕХ СОСТОЯНИЙ: если пользователь нажал кнопку меню, 
    # мы должны выйти из любого текущего диалога (add, edit, schedule)
    if user_id in user_data:
        logger.info(f"Clearing user_data for user {user_id}")
        del user_data[user_id]

    if text == "🚀 Старт":
        logger.info(f"User {user_id} selected '🚀 Старт'")
        return await start(update, context)
    elif text == "📋 Отложенные":
        logger.info(f"User {user_id} selected '📋 Отложенные'")
        return await cmd_list(update, context)
    elif text == "📊 Статистика":
        logger.info(f"User {user_id} selected '📊 Статистика'")
        return await cmd_stats(update, context)
    elif text == "📥 Добавить медиа":
        logger.info(f"User {user_id} selected '📥 Добавить медиа'")
        return await cmd_add_media(update, context)
    elif text == "📦 Пул медиа":
        logger.info(f"User {user_id} selected '📦 Пул медиа'")
        return await cmd_media_pool(update, context)
    elif text == "🗑 Сброс":
        logger.info(f"User {user_id} selected '🗑 Сброс'")
        return await cancel(update, context)
    elif text == "🗓 Планировать публикацию":
        logger.info(f"User {user_id} selected '🗓 Планировать публикацию'")
        return await cmd_schedule_daily(update, context)
    elif text == "🕐 Ежедневные":
        logger.info(f"User {user_id} selected '🕐 Ежедневные'")
        return await cmd_daily_list(update, context)
    elif text == "🔄 Рестарт":
        logger.info(f"User {user_id} selected '🔄 Рестарт'")
        return await restart_bot(update, context)
    
    logger.info(f"User {user_id} selected unknown menu item: {text}")
    return None

async def cmd_schedule_daily(update: Update, context: CallbackContext):
    """Кнопка «🗓 Планировать публикацию» — планировка только по времени без медиа и подписи."""
    await update.message.reply_text(
        "⏰ Выберите час для ежедневной публикации:",
        reply_markup=build_hour_picker("schedule")
    )
    return SCHEDULE_DAILY_HOUR

async def schedule_daily_get_hour(update: Update, context: CallbackContext):
    """Получаем час для ежедневного поста."""
    query = update.callback_query
    await query.answer()
    hour = query.data.replace("schedule_hour_", "")
    
    await query.edit_message_text(
        f"⏰ Выберите минуты (час: {hour}):",
        reply_markup=build_minute_picker("schedule", hour)
    )
    return SCHEDULE_DAILY_MINUTE

async def schedule_daily_get_minute(update: Update, context: CallbackContext):
    """Получаем минуту и создаём ежедневный пост."""
    query = update.callback_query
    await query.answer()
    data = query.data.replace("schedule_min_", "")
    parts = data.split("_")
    hour, minute = parts[0], parts[1]
    time_str = f"{hour}:{minute}"
    
    post_id = stories_db.add_post(post_type="daily", post_time=time_str, media_id=-1, caption='')
    
    await query.edit_message_text(
        f"✅ Ежедневная публикация #{post_id} запланирована на {time_str}!\n"
        f"Медиа будет выбрано случайно из пула."
    )
    return ConversationHandler.END

# ========== БЛОК ДОБАВЛЕНИЯ МЕДИА В ПУЛ ==========

async def cmd_add_media(update: Update, context: CallbackContext):
    """Команда /add_media — загрузить медиа в пул без создания поста."""
    await update.message.reply_text(
        "📥 Отправь мне фото или видео с подписью (если нужно), которое хочешь добавить в пул.\n"
        "Я сохраню его и буду использовать для рандомной публикации в сторис.\n\n"
        "Отправь /cancel для отмены."
    )
    return ADD_MEDIA_WAIT

async def handle_add_media(update: Update, context: CallbackContext):
    """Принимаем медиа для добавления в пул - медиа и подпись вместе."""
    user_id = update.effective_user.id

    logger.info(f"handle_add_media called for user {user_id}")

    if not (update.message.photo or update.message.video):
        logger.info(f"User {user_id} sent non-media message")
        await update.message.reply_text("❌ Отправь фото или видео!")
        return ADD_MEDIA_WAIT

    logger.info(f"User {user_id} sent a media file")

    # Скачиваем файл
    file_id = None
    media_type = "unknown"

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        media_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "video"

    new_file = await context.bot.get_file(file_id)
    ext = ".jpg" if media_type == "photo" else ".mp4"
    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{new_file.file_unique_id}{ext}"
    file_path = str(Path(MEDIA_DIR) / file_name)

    await new_file.download_to_drive(file_path)
    logger.info(f"✅ Медиа сохранено: {file_path}")

    # Получаем подпись (может быть пустой)
    caption = update.message.caption or ""

    # Сохраняем в БД медиа с подписью
    try:
        media_id = stories_db.add_media(
            file_path=file_path,
            file_name=file_name,
            media_type=media_type,
            caption=caption
        )
        logger.info(f"handle_add_media: media_id={media_id}, will stay in ADD_MEDIA_WAIT for more files")
    except Exception as e:
        logger.error(f"handle_add_media: ошибка сохранения в БД: {e}")
        await update.message.reply_text(f"❌ Ошибка сохранения: {e}")
        return ADD_MEDIA_WAIT

    await update.message.reply_text(
        f"✅ Медиа добавлено в пул! (ID: {media_id}, тип: {media_type})\n"
        f"Подпись: {caption or '(без подписи)'}"
        f"\n\n📤 Отправь еще или /cancel чтобы завершить"
    )
    logger.info(f"handle_add_media finished for user {user_id}, returning ADD_MEDIA_WAIT")
    return ADD_MEDIA_WAIT

async def cmd_media_pool(update: Update, context: CallbackContext):
    """Команда /media_pool — показать все медиа в пуле с кнопками удаления."""
    media_list = stories_db.get_all_media()
    logger.info(f"cmd_media_pool: найдено {len(media_list)} медиа")
    if not media_list:
        await update.message.reply_text("📭 Пул медиа пуст. Используй /add_media чтобы добавить.")
        return

    await update.message.reply_text(f"📦 Пул медиа ({len(media_list)} файлов):\n\nНажми 🗑 чтобы удалить:")

    for m in media_list:
        caption_text = m.get('caption') or '(без подписи)'
        text = (
            f"🔹 *ID: {m['id']}*\n"
            f"Тип: {m['media_type']}\n"
            f"Подпись: {caption_text[:50]}\n"
            f"Добавлено: {m['created_at']}"
        )
        buttons = [[InlineKeyboardButton("🗑 Удалить", callback_data=f"del_media_{m['id']}")]]
        reply_markup = InlineKeyboardMarkup(buttons)
        try:
            if m['media_type'] == 'photo':
                with open(m['file_path'], 'rb') as f:
                    await update.message.reply_photo(photo=f, caption=text, reply_markup=reply_markup)
            elif m['media_type'] == 'video':
                with open(m['file_path'], 'rb') as f:
                    await update.message.reply_video(video=f, caption=text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка отправки медиа #{m['id']}: {e}")
            await update.message.reply_text(text, reply_markup=reply_markup)

async def cmd_delete_media(update: Update, context: CallbackContext):
    """Команда /delete_media <ID> — удалить конкретное медиа из пула."""
    if not context.args:
        await update.message.reply_text(
            "❌ Укажи ID медиа для удаления.\n"
            "Пример: `/delete_media 5`\n\n"
            "Посмотреть ID можно через /media_pool",
            
        )
        return
    
    try:
        media_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом.")
        return
    
    media = stories_db.get_media(media_id)
    if not media:
        await update.message.reply_text(f"❌ Медиа с ID {media_id} не найдено.")
        return
    
    # Подтверждение удаления
    buttons = [
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"del_media_{media_id}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="del_media_cancel")]
    ]
    await update.message.reply_text(
        f"🗑 Удалить медиа #{media_id}?\n"
        f"Тип: {media['media_type']}\n"
        f"Подпись: {(media.get('caption') or '(без подписи)')[:50]}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def button_handler_delete_media(update: Update, context: CallbackContext):
    """Обработка подтверждения удаления медиа."""
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"button_handler_delete_media: callback_data={data}")
    
    if data == "del_media_cancel":
        try:
            await query.edit_message_caption("❌ Удаление отменено.")
        except Exception:
            await query.edit_message_text("❌ Удаление отменено.")
        return
    
    # del_media_123 (где 123 — ID медиа)
    if data.startswith("del_media_") and data != "del_media_cancel":
        try:
            media_id = int(data.replace("del_media_", ""))
            success = stories_db.delete_media(media_id)
            if success:
                try:
                    await query.edit_message_caption(f"✅ Медиа #{media_id} удалено из пула.")
                except Exception:
                    await query.edit_message_text(f"✅ Медиа #{media_id} удалено из пула.")
            else:
                try:
                    await query.edit_message_caption(f"❌ Ошибка удаления медиа #{media_id}.")
                except Exception:
                    await query.edit_message_text(f"❌ Ошибка удаления медиа #{media_id}.")
        except ValueError:
            try:
                await query.edit_message_caption("❌ Ошибка: неверный формат ID.")
            except Exception:
                await query.edit_message_text("❌ Ошибка: неверный формат ID.")


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задана переменная окружения BOT_TOKEN. "
            "Получи токен у @BotFather и укажи его в .env или окружении."
        )
    stories_db.init_db()
    logger.info("✅ Management Bot запущен...")
    
    # Добавляем глобальный обработчик для отладки ВСЕХ сообщений
    class DebugHandler:
        def __init__(self):
            self.name = "DebugHandler"
        def check_update(self, update):
            if update.message:
                user_id = update.effective_user.id if update.effective_user else "unknown"
                if update.message.text:
                    logger.debug(f"DEBUG: incoming text='{update.message.text}', user={user_id}")
                elif update.message.photo:
                    logger.debug(f"DEBUG: incoming photo message, user={user_id}")
                elif update.message.video:
                    logger.debug(f"DEBUG: incoming video message, user={user_id}")
                else:
                    logger.debug(f"DEBUG: incoming non-text message, user={user_id}")
            return False
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик диалога добавления
    conv_handler_add = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO | filters.VIDEO, handle_media)],
        states={
            CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_caption)],
            CHOOSE_PLAN: [CallbackQueryHandler(button_handler_add, pattern=r"^(plan_now|plan_daily|plan_once)$")],
            PICK_HOUR: [CallbackQueryHandler(button_handler_time, pattern=r"^(daily_hour_|once_hour_|daily_back_hour|once_back_hour)")],
            PICK_MINUTE: [CallbackQueryHandler(button_handler_time, pattern=r"^(daily_min_|once_min_|daily_back_hour|once_back_hour)")],
            PICK_CALENDAR: [CallbackQueryHandler(button_handler_time, pattern=r"^cal_(prev_|next_|day_|cancel|ignore)")],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Обработчик диалога редактирования и удаления
    conv_handler_edit = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler_edit, pattern=r"^(edit_|delete_)")
        ],
        states={
            EDIT_FIELD: [CallbackQueryHandler(button_handler_edit, pattern=r"^(field_|edit_cancel)")],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_input)],
            CONFIRM_DELETE: [CallbackQueryHandler(button_handler_edit, pattern=r"^(confirm_del_|del_cancel)")],
            EDIT_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, edit_media_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    # Обработчик диалога планировщика ежедневных публикаций
    conv_handler_schedule = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["🗓 Планировать публикацию"]), cmd_schedule_daily)],
        states={
            SCHEDULE_DAILY_HOUR: [CallbackQueryHandler(schedule_daily_get_hour, pattern=r"^schedule_hour_")],
            SCHEDULE_DAILY_MINUTE: [CallbackQueryHandler(schedule_daily_get_minute, pattern=r"^schedule_min_")],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # === ПЕРВЫМ ДОЛЖЕН БЫТЬ ОБРАБОТЧИК КНОПОК МЕНЮ ===
    # Исключаем кнопки, которые обрабатываются ConversationHandler
    menu_buttons = ["🚀 Старт", "📋 Отложенные", "📊 Статистика", "📥 Добавить медиа", "📦 Пул медиа", "🗑 Сброс", "🔄 Рестарт", "🕐 Ежедневные"]
    application.add_handler(MessageHandler(filters.Text(menu_buttons) & ~filters.COMMAND, handle_menu_buttons))
    
    # Затем все остальные обработчики
    application.add_handler(conv_handler_schedule)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", cmd_list))
    application.add_handler(CommandHandler("daily_list", cmd_daily_list))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("media_pool", cmd_media_pool))
    application.add_handler(CommandHandler("delete_media", cmd_delete_media))
    
    # Обработчики callback-кнопок
    application.add_handler(CallbackQueryHandler(button_handler_delete_media, pattern=r"^del_media_"))
    application.add_handler(CallbackQueryHandler(button_handler_delete_daily, pattern=r"^del_daily_"))
    
    # Диалоги
    conv_handler_add_media = ConversationHandler(
        entry_points=[CommandHandler("add_media", cmd_add_media)],
        states={
            ADD_MEDIA_WAIT: [
                MessageHandler(filters.PHOTO | filters.VIDEO, handle_add_media),
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                               lambda u, c: u.message.reply_text("⚠️ Пожалуйста, отправьте фото или видео для добавления в пул."))
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler_add)
    application.add_handler(conv_handler_edit)
    application.add_handler(conv_handler_add_media)
    
    application.run_polling()

if __name__ == '__main__':
    main()