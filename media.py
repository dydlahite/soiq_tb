import random

from database import cursor, db, now_iso, get_setting, set_setting
from config import DEFAULT_MEDIA_CHANCE


EXPLICIT_MEDIA_TRIGGERS = [
    "скинь картинку", "покажи картинку", "покажи фото", "скинь фото",
    "скинь мем", "покажи мем", "скинь гиф", "покажи гиф",
    "отправь картинку", "отправь фото", "отправь мем", "отправь гиф",
    "дай картинку", "дай фото", "дай мем",
]


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


def clear_media(category=None):
    if category:
        cursor.execute("DELETE FROM media WHERE category = ?", (category,))
    else:
        cursor.execute("DELETE FROM media")
    deleted = cursor.rowcount
    db.commit()
    return deleted


def clear_media_seen(chat_id=None):
    if chat_id is None:
        cursor.execute("DELETE FROM media_seen")
    else:
        cursor.execute("DELETE FROM media_seen WHERE chat_id = ?", (chat_id,))
    deleted = cursor.rowcount
    db.commit()
    return deleted


def mark_media_seen(media_id, user_id, chat_id):
    if not media_id or not chat_id:
        return

    cursor.execute(
        """
        INSERT OR IGNORE INTO media_seen (user_id, chat_id, media_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, chat_id, media_id, now_iso()),
    )
    db.commit()


def get_random_media(category=None, user_id=None, chat_id=None, allow_seen=False):
    params = []
    where = []

    if category:
        where.append("category = ?")
        params.append(category)

    if chat_id is not None and not allow_seen:
        where.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM media_seen
                WHERE media_seen.media_id = media.id
                  AND media_seen.chat_id = ?
                  AND (media_seen.user_id = ? OR media_seen.user_id IS NULL)
            )
            """
        )
        params.extend([chat_id, user_id])

    sql = "SELECT * FROM media"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY RANDOM() LIMIT 1"

    cursor.execute(sql, tuple(params))
    return cursor.fetchone()


def detect_media_category(text, mood):
    lower = text.lower()

    if any(word in lower for word in ["грустно", "плохо", "устала", "тоскливо", "болото"]):
        return "sad"

    if any(word in lower for word in ["смешно", "лол", "ахах", "мем", "прикол"]):
        return "funny"

    if any(word in lower for word in ["злюсь", "бесит", "ненавижу", "раздражает"]):
        return "angry"

    if any(word in lower for word in ["романтично", "нежно", "люблю", "скучаю"]):
        return "romantic"

    if mood in ["tired", "melancholic", "cold", "romantic"]:
        return mood

    return None


def user_explicitly_asked_media(text):
    lower = (text or "").lower()
    return any(trigger in lower for trigger in EXPLICIT_MEDIA_TRIGGERS)


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


async def send_media_item(message, item, user_id=None, chat_id=None):
    if not item:
        return False

    media_type = item["media_type"]
    sent = False

    if media_type == "sticker" and item["file_id"]:
        await message.reply_sticker(item["file_id"])
        sent = True
    elif media_type == "photo" and item["file_id"]:
        await message.reply_photo(item["file_id"], caption=item["note"] or None)
        sent = True
    elif media_type == "animation" and item["file_id"]:
        await message.reply_animation(item["file_id"], caption=item["note"] or None)
        sent = True
    elif media_type == "link" and item["url"]:
        title = item["title"] or "Ссылка"
        await message.reply_text(f"{title}\n{item['url']}")
        sent = True

    if sent:
        mark_media_seen(item["id"], user_id, chat_id)

    return sent


async def maybe_send_media(update, text, mood):
    asked = user_explicitly_asked_media(text)
    chance = get_media_chance()

    if not asked:
        if chance <= 0:
            return
        if random.randint(1, 100) > chance:
            return

    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    category = detect_media_category(text, mood)

    item = get_random_media(
        category=category,
        user_id=user_id,
        chat_id=chat_id,
        allow_seen=asked,
    )

    if not item and category:
        item = get_random_media(
            user_id=user_id,
            chat_id=chat_id,
            allow_seen=asked,
        )

    if not item:
        return

    await send_media_item(update.message, item, user_id=user_id, chat_id=chat_id)
