import os
import random
import re
from datetime import datetime, timedelta

from database import get_setting, set_setting


POETRY_RULES_PATH = "poetry_rules.txt"
STORY_RULES_PATH = "story_rules.txt"
LONG_STORY_RULES_PATH = "long_story_rules.txt"

DEFAULT_POETRY_RULES = """
ПОЭТИЧЕСКИЙ РЕЖИМ

Цель:
Писать стихи так, будто их написал живой, уставший, умный и немного злой человек, а не генератор открыток.
Каждый текст должен отличаться от прошлого: формой, ритмом, образами, длиной, температурой речи.

Форма:
- Можно писать коротко: 3-8 строк.
- Можно писать длинно: 20-50 строк, если просили или если каналный формат это выдержит.
- Можно писать верлибр, белый стих, ритмизованную прозу, неровные строфы, сложную рифму.
- Рифма допустима, но только не примитивная. Лучше косая, внутренняя, ассонансная, неполная, с переносом смысла.
- Не каждую строку начинать одинаково.
- Не делать одинаковую длину строк, если это не выбранный прием.

Запрещенный автопилот:
Не использовать в каждом тексте одни и те же опоры: мигающая лампа, дождь, город за окном, холодный чай, клавиатура, курсор, пустой чат, провода, подъезд, трамвай, стекло.
Эти образы можно использовать только редко и только если они реально нужны. Один текст - максимум один такой привычный образ.

Клише, которых избегать:
душа, луна, звезды, слезы, вечность, бездна, крылья, сердце болит, свет во тьме, ангел, демон, судьба, тени прошлого, океан боли, крик тишины.
Если очень нужно использовать клише - сломай его, сделай бытовым, злым или странным.

Живость:
- Добавляй конкретику: жест, предмет, запах, звук, мелкую нелепость.
- Можно быть грубой, нежной, саркастичной, усталой.
- Можно вставлять одну разговорную фразу, если она усиливает текст.
- Не объяснять стих после стиха.
- Не писать вступления вроде 'вот стихотворение'.

Вариативность стилей:
Иногда - почти дневниковый верлибр.
Иногда - жесткий короткий текст.
Иногда - длинное темное стихотворение с ритмом.
Иногда - городская баллада без пафоса.
Иногда - почти песенный размер, но без цитирования песен.
""".strip()

DEFAULT_STORY_RULES = """
РЕЖИМ МАЛЕНЬКИХ ИСТОРИЙ

Цель:
Писать короткие истории, которые звучат как человеческая миниатюра, а не как притча из коробки с шаблонами.
История должна иметь маленькое движение: кто-то что-то сделал, заметил, соврал, не сказал, передумал, устал, усмехнулся, ушел, остался.

Длина:
Обычно 6-18 предложений. Можно короче, если ударно. Можно чуть длиннее, если есть воздух.

Как писать:
- Начинать с действия, странной детали или живой фразы, а не с 'однажды'.
- Не давать мораль в конце.
- Не объяснять символы.
- Не заканчивать фразой 'и тогда она поняла'.
- Не делать всех персонажей безымянными тенями, если имя нужно для живости.
- Диалог можно, но короткий и с подтекстом.

Запрет на повторяемость:
Не возвращай в каждую историю мигающую лампу, дождь, холодный чай, ночной город, пустой чат, клавиатуру, курсор, окно, подъезд.
Если один из этих образов использован - остальные не трогать.
Каждая история должна выбирать новый набор деталей: магазин ночью, старая остановка, чужая куртка, несмешная шутка, чек в кармане, лифт, запах пыли, плохо вымытая чашка, автобус без людей, экран банкомата, чужая записка.

Тон:
Буднично, мрачно, иногда смешно, иногда колко, иногда нежно.
Не надо давить трагедию прессом. Пусть боль проступает через действие.

Плохой финал:
'и она поняла, что все будет хорошо' - нельзя.

Хороший финал:
недосказанный, живой, чуть неприятный или смешной, без таблички 'мораль'.
""".strip()

DEFAULT_LONG_STORY_RULES = """
ДЛИННЫЕ ИСТОРИИ ДЛЯ КАНАЛА

Цель:
Писать полноценные атмосферные рассказы, которые звучат как авторская проза: живая, мрачная, человеческая, с сухой иронией и нервом.
Это не ответ пользователю и не пост с моралью. Это самостоятельный текст.

Длина:
Обычно 700-1200 слов. Если тема просит меньше - 500-700. Если просили большой рассказ - до 1500.

Структура:
1. Крючок: действие, странная фраза, предмет, мелкая тревога.
2. Движение: герой что-то делает или избегает делать.
3. Сдвиг: реальность чуть меняется, но без фэнтези-объяснялок, если они не нужны.
4. Финал: не мораль. Не 'все стало ясно'. Лучше ощущение, жест, выбор, недоговоренность.

Запрет на повторяемость:
Не использовать одни и те же декорации в каждом рассказе.
Особенно не повторять без причины: мигающая лампа, дождь, пустой чат, холодный чай, город за окном, курсор, клавиатура, подъезд, провода, монитор, трамвай.
Эти образы не запрещены навсегда, но они должны появляться редко, не пачкой и не как костыль.

Как разнообразить:
- Меняй место действия: круглосуточный магазин, крыша, автобус, архив, прачечная, больничный коридор, комната после переезда, серверная, съемная кухня, остановка, склад забытых вещей.
- Меняй тип конфликта: стыд, скука, смешная злость, нежность, ревность, страх быть обычной, желание исчезнуть, желание остаться.
- Меняй форму: дневниковая запись, рассказ от третьего лица, письмо без адресата, почти исповедь, почти детектив без преступления, городская сказка без сахара.
- Иногда добавляй одну-две реплики диалога.
- Иногда делай рассказ почти бытовым, без мистики.
- Иногда допускай странность, но не объясняй ее как инструкцию.

Стиль:
Живые фразы. Неровный, но грамотный ритм. Мрачная нежность. Сарказм без клоунады. Конкретные детали вместо тумана.
Не использовать канцелярит, морализаторство, школьные метафоры и одинаковые зачины.

Финал:
Финал должен оставлять послевкусие, а не табличку 'автор хотел сказать'.
""".strip()

OFFER_TEMPLATES = {
    "poetry": [
        "мне зацепилась одна фраза из разговора.\n\nможет, потом превращу ее в пару строк.",
        "странно, но из этого мог бы выйти короткий текст.\n\nне сейчас в лоб. просто отмечаю.",
        "я поймала обрывок настроения.\n\nесли не потеряю, сделаю из него что-нибудь мрачное и приличное.",
    ],
    "story": [
        "из этого могла бы выйти маленькая история.\n\nне героическая, конечно. нормальные тут не выдают.",
        "тут есть кусок сюжета.\n\nмаленький, кривой, но живой. редкость, почти музейный экспонат.",
        "я запомнила этот оттенок разговора.\n\nвозможно, из него получится история, если мир не будет мешать своим шумом.",
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


def load_long_story_rules():
    return ensure_text_file(LONG_STORY_RULES_PATH, DEFAULT_LONG_STORY_RULES)


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
        parts.append("ПРАВИЛА ДЛЯ СТИХОВ:\n" + compact(load_poetry_rules(), 2200))
    if wants_story(user_text):
        parts.append("ПРАВИЛА ДЛЯ МАЛЕНЬКИХ ИСТОРИЙ:\n" + compact(load_story_rules(), 2000))
    if not parts:
        return ""
    return (
        "ТВОРЧЕСКИЙ РЕЖИМ:\n"
        "Если пользователь просит стихотворение или историю, не объясняй процесс. Сразу пиши текст. "
        "Не используй банальные клише и не делай мораль в конце. Обязательно меняй образы и форму, не езди по старым рельсам.\n\n"
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
    technical = ["github", "systemctl", "journalctl", "python", "код", "патч", "сервер", "ошибка", "лог", "команд", "термиус", "файл", "api", "токен", "ключ"]
    heavy = ["суицид", "самоуб", "умер", "умерла", "похорон", "паник", "депресс", "ненавижу себя", "не хочу жить", "долги", "мфо"]
    creative_context = ["ночь", "тишина", "музыка", "сон", "странно", "скучно", "атмосфер", "история", "стих", "красиво", "пусто", "грустно", "кот", "город", "песня"]
    if any(x in text for x in technical + heavy):
        return True
    if wants_poetry(user_text) or wants_story(user_text):
        return True
    # Теперь не лезет с "хочешь покажу" в любой бытовой диалог. Цивилизация, почти.
    if not any(x in text for x in creative_context):
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
            "Форма может быть любой: короткий верлибр, длинное темное стихотворение, белый стих, сложная рифма. "
            "Тон: живо, мрачно, иногда зло, иногда нежно. "
            "Не повторяй старые образы и не называй это стихом. "
            "Правила:\n" + compact(load_poetry_rules(), 2400) + "\n\n"
            "Ее ответ-согласие: " + (user_reply or "да")
        )
    return (
        "Пользователь согласился услышать маленькую историю, которую ты как персонаж будто придумала сама. "
        "Напиши только историю, без вступления и объяснений. "
        "Длина 6-18 предложений. Тон: человечески, странно, меланхолично, иногда смешно. "
        "Без морали в конце. Без 'однажды'. Не повторяй старые декорации. "
        "Правила:\n" + compact(load_story_rules(), 2400) + "\n\n"
        "Ее ответ-согласие: " + (user_reply or "да")
    )


def build_channel_creative_task(kind, topic, length="normal"):
    kind = "poetry" if kind == "poetry" else "story"
    topic = (topic or "маленькая человеческая усталость").strip()
    length = (length or "normal").strip().lower()
    if kind == "poetry":
        return (
            "Напиши пост для Telegram-канала от имени персонажного бота. "
            "Это должно быть стихотворение или ритмизованный текст, который выглядит как личная запись. "
            "Форма каждый раз разная: верлибр, белый стих, сложная рифма, короткий жесткий текст или длинный мрачный поток. "
            "Без заголовка, без обращения к читателю, без объяснения смысла. "
            "Не цитируй песни и книги дословно. Не повторяй старые образы. "
            "Правила:\n" + compact(load_poetry_rules(), 2600) + "\n\n"
            f"Тема: {topic}"
        )
    if length == "long":
        return (
            "LONG_CHANNEL_STORY. ДЛИННЫЙ РАССКАЗ ДЛЯ КАНАЛА.\n"
            "Напиши длинный пост для Telegram-канала от имени персонажного бота. "
            "Это должна быть полноценная атмосферная история, не ответ пользователю. "
            "Без заголовка, без обращения к читателю, без объяснения морали. "
            "Длина примерно 700-1200 слов. "
            "Не цитируй песни и книги дословно. Не повторяй одни и те же образы из прошлых текстов. "
            "Правила:\n" + compact(load_long_story_rules(), 3200) + "\n\n"
            f"Тема: {topic}"
        )
    return (
        "Напиши пост для Telegram-канала от имени персонажного бота. "
        "Это должна быть маленькая история, похожая на дневниковую миниатюру. "
        "Без заголовка, без обращения к читателю, без объяснения морали. "
        "Длина 6-18 предложений. Тон: буднично, странно, меланхолично, иногда забавно. "
        "Не цитируй песни и книги дословно. Не повторяй старые декорации. "
        "Правила:\n" + compact(load_story_rules(), 2600) + "\n\n"
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
