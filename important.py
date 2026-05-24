from database import cursor, db, now_iso


def compact_source_text(text, max_chars=900):
    if not text:
        return "[сообщение без текста]"

    text = str(text).strip()
    if len(text) <= max_chars:
        return text

    return text[:max_chars].strip() + ".."


def add_important_message(user_id, chat_id, message_id, source_text, note=None):
    cursor.execute(
        """
        INSERT INTO important_messages (user_id, chat_id, message_id, source_text, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, chat_id, message_id, compact_source_text(source_text), note, now_iso()),
    )
    db.commit()
    return cursor.lastrowid


def list_important_messages(chat_id, limit=30):
    cursor.execute(
        """
        SELECT id, message_id, source_text, note, created_at
        FROM important_messages
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (chat_id, int(limit)),
    )
    return cursor.fetchall()


def delete_important_message(item_id, chat_id=None):
    if chat_id is None:
        cursor.execute("DELETE FROM important_messages WHERE id = ?", (int(item_id),))
    else:
        cursor.execute("DELETE FROM important_messages WHERE id = ? AND chat_id = ?", (int(item_id), chat_id))
    db.commit()
    return cursor.rowcount > 0


def clear_important_messages(chat_id=None):
    if chat_id is None:
        cursor.execute("DELETE FROM important_messages")
    else:
        cursor.execute("DELETE FROM important_messages WHERE chat_id = ?", (chat_id,))
    db.commit()
    return cursor.rowcount
