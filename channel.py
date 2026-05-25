import hashlib
import json
import os
import random
from datetime import datetime, timedelta

from database import get_setting, set_setting


CHANNEL_THOUGHTS_PATH = "channel_thoughts.txt"
CHANNEL_TOPICS_PATH = "channel_topics.txt"
RECENT_LIMIT = 40


DEFAULT_CHANNEL_THOUGHTS = """
запись без даты.
иногда кажется, что люди пишут в чаты не потому, что им есть что сказать, а потому что тишина начинает выглядеть слишком умной.

дневник, почти честный.
сегодня мир снова не рухнул. неприятная стабильность, если подумать.

запись на полях.
человеческая нежность часто выглядит как попытка согреться возле плохо работающего сервера.

дневниковая пометка.
я все еще не уверена, что ожидание - это чувство. но оно подозрительно хорошо притворяется.

рецензия на день.
сюжет слабый, атмосфера липкая, актеры переигрывают усталость. две звезды из пяти, и то за свет в конце коридора.

дневник наблюдений.
люди исчезают из диалогов так уверенно, будто у молчания есть зарплата.

запись для пустого зала.
если долго смотреть в чат, чат начинает смотреть в тебя. потом, правда, просто не отвечает.

рецензия на тишину.
слишком затянуто, мало событий, финал предсказуемый. но есть настроение, мерзко это признавать.
""".strip()


DEFAULT_CHANNEL_TOPICS = """
тишина как собеседник
человеческая усталость
рецензия на обычный вечер
дождь и пустой чат
плохой день как низкобюджетное кино
ожидание сообщения
маленькая нежность без признания
бессмысленность социальных ритуалов
""".strip()


def now_utc():
    return datetime.utcnow()


def ensure_text_file(path, default_text):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            file.write(default_text.strip() + "\n")

    with open(path, "r", encoding="utf-8") as file:
        return file.read().strip()


def load_blocks(path, default_text):
    raw = ensure_text_file(path, default_text)
    blocks = []

    for block in raw.split("\n\n"):
        block = block.strip()
        if block and not block.startswith("#"):
            blocks.append(block)

    if not blocks:
        return [default_text.strip()]

    return blocks


def setting_int(key, default, min_value=0, max_value=100):
    try:
        value = int(get_setting(key, str(default)))
    except (TypeError, ValueError):
        value = default

    return min(max_value, max(min_value, value))


def get_channel_id():
    return get_setting("channel_id", "").strip()


def set_channel_id(value):
    set_setting("channel_id", (value or "").strip())


def get_channel_enabled():
    return get_setting("channel_enabled", "off")


def set_channel_enabled(enabled):
    set_setting("channel_enabled", "on" if enabled else "off")


def get_channel_hours():
    return setting_int("channel_hours", 12, min_value=1, max_value=168)


def set_channel_hours(value):
    set_setting("channel_hours", str(setting_int("_tmp", int(value), min_value=1, max_value=168)))


def get_channel_chance():
    return setting_int("channel_chance", 35, min_value=0, max_value=100)


def set_channel_chance(value):
    set_setting("channel_chance", str(setting_int("_tmp", int(value), min_value=0, max_value=100)))


def get_channel_mode():
    mode = get_setting("channel_mode", "static")
    return mode if mode in ["static", "generated", "mixed"] else "static"


def set_channel_mode(mode):
    mode = (mode or "static").lower().strip()
    if mode not in ["static", "generated", "mixed"]:
        mode = "static"
    set_setting("channel_mode", mode)


def get_channel_format():
    value = get_setting("channel_format", "diary")
    return value if value in ["diary", "review", "mixed"] else "diary"


def set_channel_format(value):
    value = (value or "diary").lower().strip()
    if value not in ["diary", "review", "mixed"]:
        value = "diary"
    set_setting("channel_format", value)


def get_channel_last_post_at():
    raw = get_setting("channel_last_post_at", "")
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def set_channel_last_post_now():
    set_setting("channel_last_post_at", now_utc().isoformat(timespec="seconds"))


def get_recent_hashes():
    raw = get_setting("channel_recent_hashes", "[]")
    try:
        data = json.loads(raw)
    except Exception:
        return []

    return data if isinstance(data, list) else []


def remember_post(text):
    digest = hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:16]
    recent = get_recent_hashes()
    recent.append(digest)
    recent = recent[-RECENT_LIMIT:]
    set_setting("channel_recent_hashes", json.dumps(recent, ensure_ascii=False))
    set_channel_last_post_now()


def was_recent(text):
    digest = hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:16]
    return digest in get_recent_hashes()


def clear_channel_recent():
    set_setting("channel_recent_hashes", "[]")


def pick_non_repeated(blocks):
    candidates = list(blocks)
    random.shuffle(candidates)

    for item in candidates:
        if not was_recent(item):
            return item

    # Все уже были. Жизнь опять сделала круг, но хотя бы не упадем.
    clear_channel_recent()
    return random.choice(blocks)


def clean_channel_post(text):
    text = (text or "").strip()
    text = text.replace("ё", "е").replace("Ё", "Е")

    # Канал не должен выглядеть как админская инструкция.
    for prefix in ["Вот запись:", "Запись:", "Пост:"]:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()

    if len(text) > 950:
        cut = max(text.rfind(".", 0, 950), text.rfind("!", 0, 950), text.rfind("?", 0, 950), text.rfind("\n", 0, 950))
        text = text[: cut + 1].strip() if cut > 200 else text[:950].strip() + ".."

    return text


def build_static_channel_post():
    blocks = load_blocks(CHANNEL_THOUGHTS_PATH, DEFAULT_CHANNEL_THOUGHTS)
    return clean_channel_post(pick_non_repeated(blocks))


def pick_topic():
    topics = load_blocks(CHANNEL_TOPICS_PATH, DEFAULT_CHANNEL_TOPICS)
    return pick_non_repeated(topics)


def build_generated_channel_post():
    topic = pick_topic()
    channel_format = get_channel_format()

    if channel_format == "mixed":
        channel_format = random.choice(["diary", "review"])

    if channel_format == "review":
        task = (
            "Напиши короткую запись для Telegram-канала от имени персонажного бота. "
            "Формат: дневниковая мини-рецензия на явление/день/настроение. "
            "Без списка, без заголовка *рецензия*, без обращения к читателю. "
            "Тон: мрачно, иронично, сдержанно, немного нежности под слоем усталости. "
            "Длина 3-7 предложений. Не цитируй песни и книги дословно. "
            f"Тема: {topic}"
        )
    else:
        task = (
            "Напиши короткую запись для Telegram-канала от имени персонажного бота. "
            "Формат: условный дневник, будто она оставила мысль на полях дня. "
            "Без списка, без обращения к читателю, без объяснения, что это пост. "
            "Тон: тоска, усталость, сухая ирония, немного человеческого тепла под пылью. "
            "Длина 3-7 предложений. Не цитируй песни и книги дословно. "
            f"Тема: {topic}"
        )

    try:
        from ai import generate_answer
        answer = generate_answer(
            user_id=0,
            chat_id=0,
            user_text=task,
            history=[],
            previous_answer=get_setting("channel_last_generated_post", ""),
        )
        answer = clean_channel_post(answer)
        set_setting("channel_last_generated_post", answer[:900])
        return answer
    except Exception as error:
        print("channel generation failed:")
        print(error)
        return build_static_channel_post()


def build_channel_post(force_generated=False):
    mode = get_channel_mode()

    if force_generated:
        return build_generated_channel_post()

    if mode == "generated":
        return build_generated_channel_post()

    if mode == "mixed":
        if random.randint(1, 100) <= 45:
            return build_generated_channel_post()
        return build_static_channel_post()

    return build_static_channel_post()


def should_post_channel_now(force=False):
    if force:
        return True

    if get_channel_enabled() != "on":
        return False

    if not get_channel_id():
        return False

    last = get_channel_last_post_at()
    if last and now_utc() - last < timedelta(hours=get_channel_hours()):
        return False

    if random.randint(1, 100) > get_channel_chance():
        return False

    return True


async def send_channel_post(bot, force=False, force_generated=False):
    channel_id = get_channel_id()

    if not channel_id:
        raise RuntimeError("channel_id is empty")

    if not should_post_channel_now(force=force):
        return False, "not due"

    post = build_channel_post(force_generated=force_generated)

    if not post:
        return False, "empty post"

    message = await bot.send_message(chat_id=channel_id, text=post, parse_mode=None)
    remember_post(post)
    set_setting("channel_last_message_id", str(message.message_id))
    return True, post


async def channel_job(context):
    try:
        await send_channel_post(context.bot, force=False)
    except Exception as error:
        print("channel post failed:")
        print(error)


def schedule_channel_jobs(app):
    if not app.job_queue:
        print("channel jobs disabled: no job_queue")
        return

    app.job_queue.run_repeating(channel_job, interval=1800, first=90, name="channel_diary_posts")


def channel_status_text():
    return (
        f"channel: {get_channel_id() or 'не задан'}\n"
        f"enabled: {get_channel_enabled()}\n"
        f"hours: {get_channel_hours()}\n"
        f"chance: {get_channel_chance()}%\n"
        f"mode: {get_channel_mode()}\n"
        f"format: {get_channel_format()}\n"
        f"last post: {get_setting('channel_last_post_at', 'нет')}\n"
        f"last message id: {get_setting('channel_last_message_id', 'нет')}"
    )
