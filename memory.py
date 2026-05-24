from database import cursor, db, now_iso


MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_ITEM_CHARS = 650
MAX_MEMORY_VALUE_CHARS = 450


def compact_text(text, max_chars=MAX_HISTORY_ITEM_CHARS):
    if not text:
        return ""

    text = str(text).strip()

    if len(text) <= max_chars:
        return text

    cut = max(
        text.rfind(".", 0, max_chars),
        text.rfind("!", 0, max_chars),
        text.rfind("?", 0, max_chars),
        text.rfind("\n", 0, max_chars),
    )

    if cut > 120:
        return text[: cut + 1].strip()

    return text[:max_chars].strip() + ".."


def save_message(user_id, chat_id, role, content):
    content = compact_text(content, max_chars=1400)

    cursor.execute(
        """
        INSERT INTO messages (user_id, chat_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, chat_id, role, content, now_iso()),
    )
    db.commit()


def get_history(user_id, chat_id, limit=MAX_HISTORY_MESSAGES):
    limit = min(int(limit or MAX_HISTORY_MESSAGES), MAX_HISTORY_MESSAGES)

    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE user_id = ? AND chat_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, chat_id, limit),
    )

    rows = cursor.fetchall()
    rows.reverse()

    history = []

    for row in rows:
        content = compact_text(row["content"])

        if content:
            history.append({"role": row["role"], "content": content})

    return history


def get_last_assistant_answer(user_id, chat_id):
    cursor.execute(
        """
        SELECT content
        FROM messages
        WHERE user_id = ? AND chat_id = ? AND role = 'assistant'
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id, chat_id),
    )

    row = cursor.fetchone()
    return row["content"] if row else ""


def clear_user_memory(user_id, chat_id):
    cursor.execute(
        "DELETE FROM messages WHERE user_id = ? AND chat_id = ?",
        (user_id, chat_id),
    )
    db.commit()


def clear_all_memory():
    cursor.execute("DELETE FROM messages")
    db.commit()


def count_messages():
    cursor.execute("SELECT COUNT(*) AS count FROM messages")
    return cursor.fetchone()["count"]


def remember(scope, key, value, user_id=None, chat_id=None):
    now = now_iso()
    value = compact_text(value, max_chars=MAX_MEMORY_VALUE_CHARS)

    cursor.execute(
        """
        INSERT OR REPLACE INTO memories (scope, user_id, chat_id, key, value, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (scope, user_id, chat_id, key, value, now, now),
    )
    db.commit()


def forget(scope, key, user_id=None, chat_id=None):
    cursor.execute(
        """
        DELETE FROM memories
        WHERE scope = ? AND key = ?
        """,
        (scope, key),
    )
    db.commit()


def list_memories(scope, user_id=None, chat_id=None):
    if scope == "global":
        cursor.execute(
            """
            SELECT key, value
            FROM memories
            WHERE scope = 'global'
            ORDER BY key
            """
        )
    else:
        cursor.execute(
            """
            SELECT key, value
            FROM memories
            WHERE scope = ? AND user_id = ? AND chat_id = ?
            ORDER BY key
            """,
            (scope, user_id, chat_id),
        )

    return [(row["key"], row["value"]) for row in cursor.fetchall()]


def build_memory_prompt(user_id, chat_id):
    global_memories = list_memories("global")
    user_memories = list_memories("user", user_id=user_id, chat_id=chat_id)

    parts = []

    if global_memories:
        lines = "\n".join([
            f"- {key}: {compact_text(value, max_chars=MAX_MEMORY_VALUE_CHARS)}"
            for key, value in global_memories[:12]
        ])
        parts.append("Глобальная память бота:\n" + lines)

    if user_memories:
        lines = "\n".join([
            f"- {key}: {compact_text(value, max_chars=MAX_MEMORY_VALUE_CHARS)}"
            for key, value in user_memories[:12]
        ])
        parts.append("Память об этом пользователе:\n" + lines)

    return "\n\n".join(parts)
