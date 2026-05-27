"""
stories_db.py — работа с базой данных для Telegram Stories.
Версия 2.0: добавлена таблица медиафайлов (media),
привязка медиа к запланированным постам, расширенные статусы.
"""
import sqlite3
import json
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional

DB_NAME = "stories_bot.db"
TIMEZONE = ZoneInfo("Europe/Moscow")  # Часовой пояс для даты использования

def init_db():
    """Создаёт/обновляет таблицы."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        # Таблица медиафайлов (загруженные фото/видео)
        cur.execute("""CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            media_type TEXT NOT NULL,  -- 'photo', 'video'
            caption TEXT,              -- подпись, если была при загрузке
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        # Таблица запланированных постов (теперь с media_id)
        cur.execute("""CREATE TABLE IF NOT EXISTS scheduled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_type TEXT NOT NULL,      -- 'now', 'daily', 'once'
            post_time TEXT NOT NULL,      -- для daily: "HH:MM", для once: "YYYY-MM-DD HH:MM"
            media_id INTEGER NOT NULL,    -- ссылка на media.id
            caption TEXT,                 -- финальный текст (может отличаться от медиа)
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_id) REFERENCES media(id)
        )""")
        # Таблица истории отправки
        cur.execute("""CREATE TABLE IF NOT EXISTS posted_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            status TEXT NOT NULL,         -- 'success', 'failed'
            error_text TEXT,
            posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES scheduled_posts(id)
        )""")
        # Таблица использования медиа сегодня (чтобы не повторять одну и ту же комбинацию media+caption в один день)
        cur.execute("""CREATE TABLE IF NOT EXISTS used_media_today (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            caption_hash TEXT NOT NULL,
            used_date TEXT NOT NULL, -- YYYY-MM-DD
            UNIQUE(media_id, caption_hash, used_date)
        )""")
        conn.commit()

# --- Медиафайлы ---
def add_media(file_path: str, file_name: str, media_type: str, caption: str = None) -> int:
    """Сохранить новый медиафайл. Возвращает ID."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""INSERT INTO media (file_path, file_name, media_type, caption)
            VALUES (?, ?, ?, ?)""", (file_path, file_name, media_type, caption))
        conn.commit()
        return cur.lastrowid

def get_media(media_id: int) -> Optional[Dict]:
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM media WHERE id=?", (media_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_all_media() -> List[Dict]:
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM media ORDER BY created_at DESC")
        return [dict(row) for row in cur.fetchall()]

# --- Посты ---
def add_post(post_type: str, post_time: str, media_id: int, caption: str) -> int:
    """Добавить запланированный пост. Возвращает ID."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""INSERT INTO scheduled_posts (post_type, post_time, media_id, caption)
            VALUES (?, ?, ?, ?)""", (post_type, post_time, media_id, caption))
        conn.commit()
        return cur.lastrowid

def get_active_posts() -> List[Dict]:
    """Получить активные посты с инфой о медиа (если media_id > 0)."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""SELECT p.*, m.file_path, m.media_type, m.file_name
            FROM scheduled_posts p
            LEFT JOIN media m ON p.media_id = m.id AND p.media_id > 0
            WHERE p.is_active=1""")
        return [dict(row) for row in cur.fetchall()]

def get_daily_posts() -> List[Dict]:
    """Получить все активные ежедневные посты, отсортированные по времени."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""SELECT p.*, m.file_path, m.media_type, m.file_name
            FROM scheduled_posts p
            LEFT JOIN media m ON p.media_id = m.id AND p.media_id > 0
            WHERE p.is_active=1 AND p.post_type='daily'
            ORDER BY p.post_time""")
        return [dict(row) for row in cur.fetchall()]

def get_post_by_id(post_id: int) -> Optional[Dict]:
    """Получить пост по ID с инфой о медиа (если media_id > 0)."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""SELECT p.*, m.file_path, m.media_type, m.file_name, m.id as media_id
            FROM scheduled_posts p
            LEFT JOIN media m ON p.media_id = m.id AND p.media_id > 0
            WHERE p.id=?""", (post_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def update_post(post_id: int, post_type: str = None, post_time: str = None, caption: str = None) -> bool:
    """Редактировать пост."""
    fields = []
    values = []
    if post_type:
        fields.append("post_type=?")
        values.append(post_type)
    if post_time:
        fields.append("post_time=?")
        values.append(post_time)
    if caption:
        fields.append("caption=?")
        values.append(caption)
    if not fields:
        return False
    values.append(post_id)
    query = f"UPDATE scheduled_posts SET {', '.join(fields)} WHERE id=?"
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(query, values)
            conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка обновления: {e}")
        return False

def update_media(media_id: int, file_path: str, media_type: str) -> bool:
    """Обновить путь к файлу и тип медиа."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("""UPDATE media SET file_path=?, media_type=? WHERE id=?""",
                         (file_path, media_type, media_id))
            conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка обновления медиа: {e}")
        return False

def deactivate_post(post_id: int) -> bool:
    """Удалить (деактивировать) пост."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("UPDATE scheduled_posts SET is_active=0 WHERE id=?", (post_id,))
            conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка удаления: {e}")
        return False

def delete_media(media_id: int) -> bool:
    """Удалить медиа из пула. Возвращает True если успешно."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            # Удаляем связанные записи из used_media_today
            conn.execute("DELETE FROM used_media_today WHERE media_id=?", (media_id,))
            # Удаляем медиа
            cur = conn.execute("DELETE FROM media WHERE id=?", (media_id,))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"Ошибка удаления медиа: {e}")
        return False

# --- История ---
def log_post(post_id: Optional[int], status: str, error_text: str = ""):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""INSERT INTO posted_history (post_id, status, error_text)
            VALUES (?, ?, ?)""", (post_id, status, error_text))
        conn.commit()

def get_stats() -> Dict:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM posted_history").fetchone()[0]
        success = cur.execute("SELECT COUNT(*) FROM posted_history WHERE status='success'").fetchone()[0]
        failed = cur.execute("SELECT COUNT(*) FROM posted_history WHERE status='failed'").fetchone()[0]
        return {"total": total, "success": success, "failed": failed}

def was_published_today(post_id: int) -> bool:
    """Проверяет, публиковался ли пост сегодня (для daily)."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
        count = cur.execute(
            "SELECT COUNT(*) FROM posted_history WHERE post_id=? AND status='success' AND DATE(posted_at)=?",
            (post_id, today)
        ).fetchone()[0]
        return count > 0

# --- Использование медиа сегодня ---
def add_used_media(media_id: int, caption_hash: str, used_date: str) -> bool:
    """Записать, что данная комбинация media+caption использована сегодня."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO used_media_today (media_id, caption_hash, used_date) VALUES (?, ?, ?)",
                         (media_id, caption_hash, used_date))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Already exists for today
        return False
    except Exception as e:
        print(f"Ошибка добавления записи used_media_today: {e}")
        return False

def is_media_used_today(media_id: int, caption_hash: str, used_date: str) -> bool:
    """Проверить, использовалась ли данная комбинация media+caption сегодня."""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("SELECT 1 FROM used_media_today WHERE media_id=? AND caption_hash=? AND used_date=?",
                           (media_id, caption_hash, used_date))
        return cur.fetchone() is not None

def get_caption_hash(caption: str) -> str:
    """Вернуть короткий хеш подписи для использования в used_media_today."""
    if not caption:
        caption = ""
    # Use MD5, take first 16 chars
    return hashlib.md5(caption.encode('utf-8')).hexdigest()[:16]

def get_random_eligible_media(caption_hash: str, used_date: str) -> Optional[Dict]:
    """Вернуть случайную медиа запись, которая сегодня еще не использовалась с данным хешем подписи.
    Если таких нет — вернуть None.
    """
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT m.* FROM media m
            WHERE NOT EXISTS (
                SELECT 1 FROM used_media_today u
                WHERE u.media_id = m.id
                  AND u.caption_hash = ?
                  AND u.used_date = ?
            )
            ORDER BY RANDOM()
            LIMIT 1
        """, (caption_hash, used_date))
        row = cur.fetchone()
        return dict(row) if row else None

def cleanup_old_used_media():
    """Удалить записи из used_media_today старше 2 дней."""
    from datetime import timedelta
    cutoff = (datetime.now(TIMEZONE) - timedelta(days=2)).strftime("%Y-%m-%d")
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM used_media_today WHERE used_date < ?", (cutoff,))
        conn.commit()

# Инициализация
init_db()
cleanup_old_used_media()
print("✅ База данных Stories v2.1 (с учетом использования медиа сегодня) инициализирована")