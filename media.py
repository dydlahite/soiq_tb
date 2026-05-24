import random

from database import cursor, db, now_iso, get_setting, set_setting
from config import DEFAULT_MEDIA_CHANCE


def add_media(media_type, category, file_id=None, url=None, title=None, trigger=None, note=None):
    cursor.execute(
        """
        INSERT INTO media (media_type, category, trigger, file_id, url, title, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (media_type, category, trigger, file_id, url, title, note, now_iso()),
    )
    db.commit()


def list_media_categories():
    cursor.execute(
        """
        SELECT category, media_type, COUNT(*) AS count
        FROM media
        GROUP BY category, media_type
        ORDER BY category, media_type
        """
    )

    return cursor.fetchall()


def list_media_items(limit=30):
    cursor.execute(
        """
        SELECT id, media_type, category, title, url, trigger
        FROM media
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def delete_media(media_id):
    cursor.execute("DELETE FROM media WHERE id = ?", (media_id,))
    db.commit()
    return cursor.rowcount > 0


def get_random_media(category=None):
    if category:
        cursor.execute(
            """
            SELECT *
            FROM media
            WHERE category = ?
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (category,),
        )
    else:
        cursor.execute(
            """
            SELECT *
            FROM media
            ORDER BY RANDOM()
            LIMIT 1
            """
        )

    return cursor.fetchone()


def detect_media_category(text, mood):
    lower = text.lower()

    if any(word in lower for word in ["грустно", "плохо", "устала", "тоскливо", "болото"]):
        return "sad"

    if any(word in lower for word in ["смешно", "лол", "ахах", "мем", "прикол"]):
        return "funny"

    if any(word in lower for word in ["злюсь", "бесит", "ненавижу", "раздражает"]):
        return "angry"

    if mood in ["tired", "melancholic", "cold"]:
        return mood

    return None


def get_media_chance():
    raw = get_setting("media_chance", str(DEFAULT_MEDIA_CHANCE))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_MEDIA_CHANCE

    return max(0, min(value, 100))


def set_media_chance(value):
    value = max(0, min(int(value), 100))
    set_setting("media_chance", str(value))


async def maybe_send_media(update, text, mood):
    chance = get_media_chance()

    if chance <= 0:
        return

    if random.randint(1, 100) > chance:
        return

    category = detect_media_category(text, mood)
    item = get_random_media(category) if category else get_random_media()

    if not item:
        return

    media_type = item["media_type"]

    if media_type == "sticker" and item["file_id"]:
        await update.message.reply_sticker(item["file_id"])
    elif media_type == "photo" and item["file_id"]:
        await update.message.reply_photo(item["file_id"], caption=item["note"] or None)
    elif media_type == "animation" and item["file_id"]:
        await update.message.reply_animation(item["file_id"], caption=item["note"] or None)
    elif media_type == "link" and item["url"]:
        title = item["title"] or "Ссылка"
        await update.message.reply_text(f"{title}\n{item['url']}")
