#!/usr/bin/env python3
"""
Stories Publisher (Публикатор).
Работает как Юзербот (от твоего имени).
Проверяет базу данных, находит запланированные посты и публикует их.
Теперь медиа выбирается случайно из всех загруженных, но с условием,
что одна и та же комбинация (медиа + подпись) не публикуется более одного раза в день.
"""
import logging
import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.functions.stories import SendStoryRequest
from telethon.tl.types import InputMediaUploadedPhoto, InputMediaUploadedDocument, InputPeerSelf, InputPrivacyValueAllowAll

import stories_db

# --- Конфигурация (заполни!) ---
API_ID = 24971873
API_HASH = "22807b277633e16075b127432368278e"
SESSION_NAME = "stories_session"
CHECK_INTERVAL = 30  # Проверять базу каждые 30 секунд
TIMEZONE = ZoneInfo("Europe/Moscow")  # Часовой пояс для планирования
# -----------------------------

# Default signature (loaded from file)
DEFAULT_SIGNATURE_TEXT = ""

def load_default_signature():
    global DEFAULT_SIGNATURE_TEXT
    try:
        with open(signature_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            DEFAULT_SIGNATURE_TEXT = data.get("text", "")
    except Exception as e:
        logger.warning(f"Не удалось загрузить default подпись: {e}")
        DEFAULT_SIGNATURE_TEXT = ""


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client: TelegramClient = None

def get_today_date_str() -> str:
    """Возвращает сегодняшнюю дату в формате YYYY-MM-DD согласно TIMEZONE."""
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

async def publish_story(post: dict) -> bool:
    """Публикует одну историю, выбирая случайное подходящее медиа из пула.
    Правила:
    - Для daily с media_id=-1: случайное медиа из пула, без повторов в рамках дня
    - Для now/once с media_id=-1: случайное медиа из пула, сброс каждый день
    - Для остальных: конкретное медиа или случайное из пула (с памятью)
    - Если медиа закончились → пропуск (return False), пост остаётся активным
    """
    global client
    if not client or not client.is_connected():
        logger.error("❌ Клиент не подключен!")
        return False

    post_id = post['id']
    caption = post['caption'] or ""
    post_type = post['post_type']
    post_media_id = post.get('media_id', 0)

    # Подпись (signature) — доп.текст с ссылкой, если указана
    signature_text = ""
    signature_id = post.get('signature_id', 0)
    if signature_id and signature_id > 0:
        sig = stories_db.get_signature(signature_id)
        if sig:
            signature_text = sig.get('text') or ""
    # Если нет конкретной подписи, используем default подпись
    if not signature_text:
        signature_text = DEFAULT_SIGNATURE_TEXT

    # Объединяем контентный caption и подпись
    if signature_text:
        if caption:
            caption = f"{caption}\n\n{signature_text}"
        else:
            caption = signature_text

    caption_hash = stories_db.get_caption_hash(caption)
    used_date = get_today_date_str()

    media_info = None

    # Для daily с media_id=-1: случайное медиа из пула с памятью
    if post_type == 'daily' and post_media_id == -1:
        media_info = stories_db.get_random_eligible_media(caption_hash, used_date)
        if not media_info:
            logger.info(f"🔸 Все медиа использованы сегодня для поста #{post_id}. Пропуск.")
            return False
    elif post_type in ('now', 'once') and post_media_id == -1:
        # Для now/once: случайное медиа с памятью (сброс каждый день через used_media_today)
        media_info = stories_db.get_random_eligible_media(caption_hash, used_date)
        if not media_info:
            logger.info(f"🔸 Все медиа использованы сегодня для поста #{post_id}. Пропуск.")
            return False
    else:
        # Для остальных постов — конкретное медиа
        if post_media_id and post_media_id > 0:
            media_info = stories_db.get_media(post_media_id)
            if not media_info:
                logger.error(f"❌ Медиа #{post_media_id} не найдено для поста #{post_id}")
                stories_db.log_post(post_id, "failed", "Media not found")
                stories_db.deactivate_post(post_id)
                return False

        # Если медиа не привязано — случайное из пула (с памятью)
        if not media_info:
            media_info = stories_db.get_random_eligible_media(caption_hash, used_date)
            if not media_info:
                logger.info(f"🔸 Все медиа использованы сегодня для поста #{post_id}. Пропуск.")
                return False

    file_path = media_info['file_path']
    media_type = media_info['media_type']
    media_id = media_info['id']

    logger.info(f"📸 Публикация истории #{post_id} (media_id={media_id}, {media_type})...")
    try:
        peer = InputPeerSelf()
        privacy = [InputPrivacyValueAllowAll()]

        if media_type == "photo":
            media = await client.upload_file(file_path)
            await client(SendStoryRequest(
                peer=peer,
                media=InputMediaUploadedPhoto(file=media),
                caption=caption,
                privacy_rules=privacy
            ))
        elif media_type == "video":
            media = await client.upload_file(file_path)
            await client(SendStoryRequest(
                peer=peer,
                media=InputMediaUploadedDocument(file=media, mime_type='video/mp4', attributes=[]),
                caption=caption,
                privacy_rules=privacy
            ))
        else:
            raise ValueError(f"Неизвестный тип медиа: {media_type}")

        logger.info(f"  ✅ История #{post_id} опубликована!")
        stories_db.log_post(post_id, "success")
        # Отмечаем использование этой комбинации сегодня
        stories_db.add_used_media(media_id, caption_hash, used_date)
        # Если это не daily, отключаем пост после публикации
        if post_type != 'daily':
            stories_db.deactivate_post(post_id)
        return True
    except Exception as e:
        logger.error(f"  ❌ Ошибка публикации #{post_id}: {e}")
        stories_db.log_post(post_id, "failed", str(e))
        return False

async def main_loop():
    """Главный цикл проверки и публикации."""
    global client

    # Инициализация БД
    stories_db.init_db()
    load_default_signature()

    # Старт клиента
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    logger.info(f"✅ Publisher запущен от имени: {me.first_name}")
    logger.info(f"⏰ Проверка новых постов каждые {CHECK_INTERVAL} сек...")

    while True:
        try:
            now = datetime.now(TIMEZONE)
            current_time = now.strftime("%H:%M")

            # Получаем активные посты
            posts = stories_db.get_active_posts()
            logger.info(f"🔍 Проверка в {current_time}: найдено {len(posts)} активных постов")

            for post in posts:
                post_id = post['id']
                post_type = post['post_type']
                post_time = post['post_time']
                should_publish = False

                # Логика определения времени публикации
                if post_type == 'now' or (post_type == 'once' and post_time == 'now'):
                    should_publish = True
                elif post_type == 'daily':
                    # Публикуем если текущее время >= запланированного И ещё не публиковали сегодня
                    try:
                        target_h, target_m = map(int, post_time.split(':'))
                        now_minutes = now.hour * 60 + now.minute
                        target_minutes = target_h * 60 + target_m
                        if now_minutes >= target_minutes and not stories_db.was_published_today(post_id):
                            should_publish = True
                    except Exception:
                        pass
                elif post_type == 'once':
                    try:
                        target_dt = datetime.strptime(post_time, "%Y-%m-%d %H:%M").replace(tzinfo=TIMEZONE)
                        if now >= target_dt:
                            should_publish = True
                    except Exception:
                        pass

                if should_publish:
                    await publish_story(post)
                    await asyncio.sleep(2)  # Пауза между публикациями

        except Exception as e:
            logger.error(f"❌ Ошибка в цикле: {e}")

        # Ждем перед следующей проверкой
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Остановка Publisher...")
    finally:
        if client and client.is_connected():
            client.disconnect()