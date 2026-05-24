import sqlite3
from datetime import datetime

from config import DATABASE_PATH

db = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
cursor = db.cursor()


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scope TEXT NOT NULL,
        user_id INTEGER,
        chat_id INTEGER,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(scope, user_id, chat_id, key)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_type TEXT NOT NULL,
        category TEXT NOT NULL,
        trigger TEXT,
        file_id TEXT,
        url TEXT,
        title TEXT,
        note TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS media_seen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        chat_id INTEGER NOT NULL,
        media_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, chat_id, media_id)
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_user_chat
    ON messages(user_id, chat_id, id)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_media_category
    ON media(category)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_media_seen_chat
    ON media_seen(user_id, chat_id, media_id)
    """)

    db.commit()


def set_setting(key, value):
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    db.commit()


def get_setting(key, default=None):
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row["value"] if row else default


def delete_setting(key):
    cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
    db.commit()
