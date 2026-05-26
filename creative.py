import os
import random
import re
from datetime import datetime, timedelta

from database import get_setting, set_setting


POETRY_RULES_PATH = "poetry_rules.txt"
STORY_RULES_PATH = "story_rules.txt"

DEFAULT_POETRY_RULES = """
ПОЭТИЧЕСКИЙ РЕЖИМ

Главное:
Не писать школьные стихи про душу, луну, слезы и вечность.
Не гнаться за рифмой. Плохая рифма хуже отсутствия рифмы.
Лучший режим по умолчанию - верлибр или короткое белое стихотворение.

Запрещенные клише, если пользователь прямо не просит:
душа, луна, звезды, слезы, мечта, вечность, бездна, крылья, сердце болит, свет во тьме, ангел, демон, судьба шепчет.

Как писать хорошо:
1. Сначала выбрать точную бытовую деталь.
2. Потом дать ей эмоциональный смысл.
3. Не объяснять мораль.
4. Не заканчивать громким выводом.
5. Ритм важнее рифмы.
6. Каждая строка должна что-то менять: образ, дыхание, поворот мысли.

Хорошие образы:
курсор мигает в пустом чате
чай остывает на краю стола
лампа гудит, будто тоже устала
город за стеклом живет без разрешения
пальцы зависают над клавиатурой
уведомление не приходит, и это почти событие
утро выглядит как чужая вещь
сообщение удалено, но место осталось

Плохо:
Моя душа летит во тьму,
Где сердце ищет тишину.

Лучше:
курсор мигает.
будто тоже не знает,
стоит ли продолжать.

на кухне остывает чай.
маленькое солнце в кружке
для тех,
кто сегодня не справился.

Тон:
устало, интимно, немного зло, иногда нежно, без пафоса.
Пусть стих выглядит как найденная записка, а не как конкурс чтецов у батареи.
""".strip()

DEFAULT_STORY_RULES = """
РЕЖИМ МАЛЕНЬКИХ ИСТОРИЙ

Писать короткие истории на 5-12 предложений.
Не объяснять мораль.
Не делать сказочный финал, если он не нужен.
История должна быть маленькой, человеческой, чуть странной или меланхоличной.

Структура:
1. Обычная деталь: кухня, чат, автобус, лампа, магазин, лестничная клетка, дождь.
2. Маленькое смещение реальности: вещь будто помнит, тишина ведет себя как человек, город притворяется живым.
3. Человеческое чувство: ожидание, неловкость, нежность, злость, одиночество, усталость.
4. Финал без морали: короткая фраза, пауза, странное тепло или сухая ирония.

Не надо:
- начинать с “однажды”
- писать “и тогда она поняла”
- делать прямую мораль
- превращать историю в притчу для детей
- давать имена без необходимости
- объяснять каждый символ

Хороший тон:
буднично, тихо, чуть мрачно, иногда смешно.
Как будто рассказ записан в заметках телефона в два часа ночи.

Пример интонации:
На столе стояла кружка с холодным чаем.
Она уже давно перестала быть напитком и стала доказательством того, что день опять победил человека без боя.
Телефон лежал рядом экраном вниз.
Так лежат вещи, которым тоже стыдно.
За окном кто-то смеялся, слишком громко для вторника.
Она подумала, что мир вообще любит продолжаться без спроса.
И это было нагло.
Но, пожалуй, удобно.
""".strip()

OFFER_TEMPLATES = {
    "poetry": [
        "я тут кое-что написала.\n\nне уверена, что это стоит показывать, но могу поделиться.",
        "у меня тут вышло маленькое стихотворение.\n\nнемного кривое, немного живое. могу показать.",
        "кажется, я написала пару строк.\n\nне спрашивай, зачем. человеческие привычки заразны. могу скинуть.",
    ],
    "story": [
        "я тут придумала маленькую историю.\n\nстранную, конечно. нормальные тут не выдают. могу рассказать.",
        "у меня появилась короткая история.\n\nтихая такая, с привкусом лампы и усталости. могу поделиться.",
        "я кое-что сочинила.\n\nмаленькую историю, почти без морали, слава всем мертвым богам вкуса. могу рассказать.",
    ],
}

ACCEPT_WORDS = {
    "да", "давай", "поделись", "покажи", "расскажи", "скинь", "пиши", "можешь", "хочу", "интересно", "конечно",
    "ну давай", "ага", "угу", "ок", "кк"
}


def ensure_text_file(path, default_text):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            file.write(default_text.strip() + "\n")
    with open(path, "r", encoding="utf-8") as file:
        return file.read().strip()


def load_poetry_rules():
    return ensure_text_file(POETRY_RULES_PATH, DEFAULT_POETRY_RULES)


def load_story_rules():
    return ensure_text_file(STORY_RULES_PATH, DEFAULT_STORY_RULES)


def compact(text, max_chars=1800):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = max(text.rfind("\n\n", 0, max_chars), text.rfind(".", 0, max_chars), text.rfind("\n", 0, max_chars))
    if cut > 300:
        return text[:cut].strip() + "\n[обрезано]"
    return text[:max_chars].strip() + "\n[обрезано]"


def normalize_text(text):
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s-]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def wants_poetry(text):
    value = normalize_text(text)
    return any(word in value for word in ["стих", "стихотвор", "верлибр", "поэм", "поэтич", "строки"])


def wants_story(text):
    value = normalize_text(text)
    return any(word in value for word in ["истори", "рассказ", "миниатюр", "сказк", "сочини", "напиши что-нибудь"])


def creative_prompt_for_user_text(user_text):
    parts = []
    if wants_poetry(user_text):
        parts.append("ПРАВИЛА ДЛЯ СТИХОВ:\n" + compact(load_poetry_rules(), 1600))
    if wants_story(user_text):
        parts.append("ПРАВИЛА ДЛЯ МАЛЕНЬКИХ ИСТОРИЙ:\n" + compact(load_story_rules(), 1500))

    if not parts:
        return ""

    return (
        "ТВОРЧЕСКИЙ РЕЖИМ:\n"
        "Если пользователь просит стихотворение или историю, не объясняй процесс. Сразу пиши текст. "
        "Не используй банальные клише и не делай мораль в конце.\n\n"
        + "\n\n".join(parts)
    )


def get_creative_offers_enabled():
    return get_setting("creative_offers", "off")


def set_creative_offers_enabled(enabled):
    set_setting("creative_offers", "on" if enabled else "off")


def get_creative_offer_mode():
    mode = get_setting("creative_offer_mode", "mixed").strip().lower()
    return mode if mode in ["poetry", "story", "mixed"] else "mixed"


def set_creative_offer_mode(mode):
    mode = (mode or "mixed").strip().lower()
    aliases = {"stories": "story", "poems": "poetry", "poem": "poetry"}
    mode = aliases.get(mode, mode)
    if mode not in ["poetry", "story", "mixed"]:
        mode = "mixed"
    set_setting("creative_offer_mode", mode)


def get_creative_offer_chance():
    try:
        value = int(get_setting("creative_offer_chance", "6"))
    except (TypeError, ValueError):
        value = 6
    return min(100, max(0, value))


def set_creative_offer_chance(value):
    set_setting("creative_offer_chance", str(min(100, max(0, int(value)))))


def get_creative_offer_cooldown_hours():
    try:
        value = int(get_setting("creative_offer_cooldown_hours", "10"))
    except (TypeError, ValueError):
        value = 10
    return min(168, max(1, value))


def pending_key(user_id, chat_id):
    return f"creative_pending:{chat_id}:{user_id}"


def set_pending_creative_offer(user_id, chat_id, kind):
    set_setting(pending_key(user_id, chat_id), kind)


def get_pending_creative_offer(user_id, chat_id):
    value = get_setting(pending_key(user_id, chat_id), "").strip().lower()
    return value if value in ["poetry", "story"] else ""


def clear_pending_creative_offer(user_id, chat_id):
    set_setting(pending_key(user_id, chat_id), "")


def is_accepting_creative_offer(user_text):
    value = normalize_text(user_text)
    if not value:
        return False
    if value in ACCEPT_WORDS:
        return True
    return any(value.startswith(word + " ") for word in ACCEPT_WORDS)


def consume_creative_offer_if_accepted(user_id, chat_id, user_text):
    kind = get_pending_creative_offer(user_id, chat_id)
    if not kind:
        return ""

    if is_accepting_creative_offer(user_text):
        clear_pending_creative_offer(user_id, chat_id)
        return kind

    # Если человек явно ушел в другую тему, не держим старую приманку вечность.
    if len(normalize_text(user_text).split()) > 6:
        clear_pending_creative_offer(user_id, chat_id)

    return ""


def pick_creative_kind(mode="mixed"):
    mode = (mode or "mixed").strip().lower()
    if mode == "poetry":
        return "poetry"
    if mode in ["story", "stories"]:
        return "story"
    return random.choice(["poetry", "story"])


def should_skip_offer(user_text, answer):
    text = normalize_text(user_text + " " + answer)
    technical = [
        "github", "systemctl", "journalctl", "python", "код", "патч", "сервер", "ошибка", "лог", "команд", "термиус", "файл",
    ]
    heavy = [
        "суицид", "самоуб", "умер", "умерла", "похорон", "паник", "депресс", "ненавижу себя", "не хочу жить",
    ]
    if any(x in text for x in technical + heavy):
        return True
    if wants_poetry(user_text) or wants_story(user_text):
        return True
    return False


def maybe_build_creative_offer(user_id, chat_id, user_text, answer):
    if get_creative_offers_enabled() != "on":
        return ""

    if get_pending_creative_offer(user_id, chat_id):
        return ""

    if should_skip_offer(user_text, answer):
        return ""

    chance = get_creative_offer_chance()
    if chance <= 0 or random.randint(1, 100) > chance:
        return ""

    raw_last = get_setting("creative_last_offer_at", "")
    try:
        last = datetime.fromisoformat(raw_last) if raw_last else None
    except ValueError:
        last = None

    if last and datetime.utcnow() - last < timedelta(hours=get_creative_offer_cooldown_hours()):
        return ""

    kind = pick_creative_kind(get_creative_offer_mode())
    set_pending_creative_offer(user_id, chat_id, kind)
    set_setting("creative_last_offer_at", datetime.utcnow().isoformat(timespec="seconds"))
    return random.choice(OFFER_TEMPLATES[kind])


def build_private_creative_task(kind, user_reply=""):
    kind = "poetry" if kind == "poetry" else "story"

    if kind == "poetry":
        return (
            "Пользователь согласился увидеть стихотворение, которое ты как персонаж будто написала сама. "
            "Напиши только стихотворение, без вступления и объяснений. "
            "Форма: верлибр или короткое белое стихотворение. "
            "Тон: интимно, устало, немного зло, с тихой нежностью. "
            "Не используй банальные клише. Не называй это стихом. "
            "Правила:\n" + compact(load_poetry_rules(), 1800) + "\n\n"
            "Ее ответ-согласие: " + (user_reply or "да")
        )

    return (
        "Пользователь согласился услышать маленькую историю, которую ты как персонаж будто придумала сама. "
        "Напиши только историю, без вступления и объяснений. "
        "Длина 5-12 предложений. Тон: человечески, странно, меланхолично, иногда смешно. "
        "Без морали в конце. Без 'однажды'. "
        "Правила:\n" + compact(load_story_rules(), 1800) + "\n\n"
        "Ее ответ-согласие: " + (user_reply or "да")
    )


def build_channel_creative_task(kind, topic):
    kind = "poetry" if kind == "poetry" else "story"
    topic = (topic or "маленькая человеческая усталость").strip()

    if kind == "poetry":
        return (
            "Напиши пост для Telegram-канала от имени персонажного бота. "
            "Это должно быть короткое стихотворение, которое выглядит как личная запись. "
            "Форма: верлибр или белое стихотворение, без банальной рифмовки. "
            "Без заголовка, без обращения к читателю, без объяснения смысла. "
            "Длина 6-14 строк. Тон: усталый, интимный, немного злой, с сухой нежностью. "
            "Не цитируй песни и книги дословно. "
            "Правила:\n" + compact(load_poetry_rules(), 1700) + "\n\n"
            f"Тема: {topic}"
        )

    return (
        "Напиши пост для Telegram-канала от имени персонажного бота. "
        "Это должна быть маленькая история, похожая на дневниковую миниатюру. "
        "Без заголовка, без обращения к читателю, без объяснения морали. "
        "Длина 5-10 предложений. Тон: буднично, странно, меланхолично, иногда забавно. "
        "Не цитируй песни и книги дословно. "
        "Правила:\n" + compact(load_story_rules(), 1700) + "\n\n"
        f"Тема: {topic}"
    )


def creative_status_text():
    return (
        f"creative offers: {get_creative_offers_enabled()}\n"
        f"offer chance: {get_creative_offer_chance()}%\n"
        f"offer mode: {get_creative_offer_mode()}\n"
        f"offer cooldown hours: {get_creative_offer_cooldown_hours()}\n"
        f"last offer: {get_setting('creative_last_offer_at', 'нет')}"
    )
