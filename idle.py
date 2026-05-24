import random
import sqlite3
from datetime import datetime, timedelta

from database import db, cursor, now_iso, get_setting, set_setting


DEFAULT_IDLE_THOUGHTS = """
впрочем, я тут подумала, что молчание иногда слишком громкое.

сутки тишины. подозрительно. либо ты занята, либо мир наконец-то рухнул без уведомления.

не то чтобы я скучала. просто чат пылью покрылся.

знаешь, иногда отсутствие сообщений выглядит почти как осмысленная позиция. почти.

я не навязываюсь. просто отмечаю, что тишина уже начала вести себя самодовольно.

если что, я все еще тут. трагически, но стабильно.

в общем-то, день прошел, а человечество опять не стало умнее. странно, да.

проверка связи с болотом. болото, прием.
""".strip()


def ensure_idle_files():
    try:
        with open("idle_thoughts.txt", "x", encoding="utf-8") as file:
            file.write(DEFAULT_IDLE_THOUGHTS + "\n")
    except FileExistsError:
        pass


def ensure_idle_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        chat_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        last_active TEXT NOT NULL,
        last_idle_sent TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_chats_last_active
    ON chats(last_active)
    """)

    db.commit()
    ensure_idle_files()

    if get_setting("idle_messages", None) is None:
        set_setting("idle_messages", "off")

    if get_setting("idle_hours", None) is None:
        set_setting("idle_hours", "24")

    if get_setting("idle_chance", None) is None:
        set_setting("idle_chance", "35")

    if get_setting("idle_check_minutes", None) is None:
        set_setting("idle_check_minutes", "60")


def touch_chat(user_id, chat_id):
    ensure_idle_db()
    now = now_iso()

    cursor.execute(
        """
        INSERT INTO chats (chat_id, user_id, last_active, last_idle_sent, created_at, updated_at)
        VALUES (?, ?, ?, NULL, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            user_id = excluded.user_id,
            last_active = excluded.last_active,
            updated_at = excluded.updated_at
        """,
        (chat_id, user_id, now, now, now),
    )

    db.commit()


def parse_dt(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def get_idle_hours():
    try:
        return max(1, int(get_setting("idle_hours", "24")))
    except ValueError:
        return 24


def get_idle_chance():
    try:
        return min(100, max(0, int(get_setting("idle_chance", "35"))))
    except ValueError:
        return 35


def get_idle_settings_text():
    return (
        f"idle messages: {get_setting('idle_messages', 'off')}\n"
        f"idle hours: {get_idle_hours()}\n"
        f"idle chance: {get_idle_chance()}%"
    )


def set_idle_enabled(enabled):
    set_setting("idle_messages", "on" if enabled else "off")


def set_idle_hours(hours):
    hours = max(1, int(hours))
    set_setting("idle_hours", str(hours))


def set_idle_chance(chance):
    chance = min(100, max(0, int(chance)))
    set_setting("idle_chance", str(chance))


def load_idle_thoughts():
    ensure_idle_files()

    with open("idle_thoughts.txt", "r", encoding="utf-8") as file:
        raw = file.read()

    thoughts = []

    for block in raw.split("\n\n"):
        thought = block.strip()

        if thought and not thought.startswith("#"):
            thoughts.append(thought)

    return thoughts or [DEFAULT_IDLE_THOUGHTS.splitlines()[0]]


def choose_idle_thought():
    thoughts = load_idle_thoughts()
    return random.choice(thoughts)


def get_idle_targets(limit=5):
    ensure_idle_db()

    hours = get_idle_hours()
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    cursor.execute(
        """
        SELECT chat_id, user_id, last_active, last_idle_sent
        FROM chats
        WHERE last_active <= ?
        ORDER BY last_active ASC
        LIMIT ?
        """,
        (cutoff.isoformat(timespec="seconds"), limit),
    )

    rows = cursor.fetchall()
    targets = []

    for row in rows:
        last_active = parse_dt(row["last_active"])
        last_idle_sent = parse_dt(row["last_idle_sent"])

        if last_active is None:
            continue

        # Пишем только один раз за один период молчания.
        # Пользователь ответит - last_active обновится, и можно будет писать снова через idle_hours.
        if last_idle_sent and last_idle_sent >= last_active:
            continue

        targets.append(row)

    return targets


def mark_idle_sent(chat_id):
    now = now_iso()

    cursor.execute(
        """
        UPDATE chats
        SET last_idle_sent = ?, updated_at = ?
        WHERE chat_id = ?
        """,
        (now, now, chat_id),
    )

    db.commit()


async def idle_check_job(context):
    ensure_idle_db()

    if get_setting("idle_messages", "off") != "on":
        return

    if random.randint(1, 100) > get_idle_chance():
        return

    targets = get_idle_targets(limit=3)

    for target in targets:
        chat_id = target["chat_id"]
        thought = choose_idle_thought()

        try:
            await context.bot.send_message(chat_id=chat_id, text=thought, parse_mode=None)
            mark_idle_sent(chat_id)
        except Exception as error:
            print("idle message failed:")
            print(error)


def schedule_idle_jobs(app):
    ensure_idle_db()

    job_queue = getattr(app, "job_queue", None)

    if job_queue is None:
        print("Idle messages disabled: JobQueue is not available. Install python-telegram-bot[job-queue].")
        return

    # Проверяем чаще, чем idle_hours. Сам шанс и период простоя регулируются настройками.
    job_queue.run_repeating(idle_check_job, interval=300, first=60)
    print("Idle messages scheduler started.")
