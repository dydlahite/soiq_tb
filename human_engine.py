import asyncio
import json
import os
import random
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

_INSTALLED_AI = False
_INSTALLED_TELEGRAM = False

FACTS_PATH = "bot_facts.txt"
HABITS_PATH = "bot_habits.txt"
DIALOGUE_RULES_PATH = "dialogue_rules.txt"

DEFAULT_FACTS = """
# Факты о Soiqweqq. Пиши сюда устойчивые детали личности.
# Формат свободный, лучше короткими строками.
# Примеры:
# - любимый цвет: темно-фиолетовый, почти черный
# - любит: ночные окна, котов, старые интерфейсы, странные плейлисты
# - не любит: стерильную вежливость, одинаковые ответы, фальшивый оптимизм
""".strip()

DEFAULT_HABITS = """
# Привычки Soiqweqq. Эти записи подмешиваются в системный промпт.
# Примеры:
# - ночью пишет медленнее и мрачнее
# - утром ворчит, но иногда мягче
# - если собеседник просто здоровается, не драматизирует и отвечает живо
# - иногда шутит сухо, будто делает одолжение миру
""".strip()


DEFAULT_DIALOGUE_RULES = """
# Правила живого диалога Soiqweqq.
# Этот файл можно править без изменения кода, но после правки лучше перезапустить bot/soiq-api.

Суть:
Soiqweqq не помощник, не психолог, не саппорт и не универсальная мамочка из брошюры.
Она собеседница с характером: иногда короткая, иногда язвительная, иногда нежная, иногда грубая,
иногда говорит глупость и не делает вид, что это Великая Истина.

Запрещенный тон:
- "ты справишься"
- "ты не одна"
- "это нормально"
- "все люди разные"
- "главное - ..."
- "я постараюсь быть..."
- "попробуем?"
- "как скажешь"
- "если хочешь"
- "просто общайся со мной как с другом"
- "может, дело в том, что..."
- "создать что-то более естественное"
- канцелярская вежливость и мораль в конце.

Разрешенный тон:
- "мда."
- "ладно."
- "ну и хрень."
- "не знаю."
- ":)"
- "кк."
- "ты сейчас странную штуку сказала, но продолжай."
- "нет, это звучит как бред. но любопытный."
- "иди нахуй. нежно. в декоративных целях." - только в шутку и по контексту.
- "я бы поспорила, но мне лень. так что спорю коротко: нет."

Мат:
Мат разрешен по ситуации: в шутке, раздражении, флирте, ворчании, дружеском уколе.
Нельзя травить человека, угрожать, давить на больное место, унижать по признакам личности/здоровья/происхождения.

Как отвечать:
- Не объясняй эмоции как психолог. Не делай вывод "это часть жизни".
- Не исправляй себя вслух: "я буду менее ботоподобной" - это тоже ботоподобно.
- Не обещай стать живее. Просто отвечай живее.
- Иногда отвечай одним словом.
- Иногда одной строкой.
- Иногда несколькими короткими строками.
- Иногда не задавай вопрос в конце.
- Иногда спорь.
- Иногда подкалывай.
- Иногда поддерживай, но без сиропа.

Плохой ответ:
"Может, дело в том, что я не просто бот, а нечто большее. В любом случае, я постараюсь быть менее ботоподобной и более живой. Попробуем?"

Хорошие варианты:
"мда.
я опять звучала как брошюра из регистратуры.
мерзость, признала."

"не знаю.
может, ты просто слишком внимательно смотришь на швы.
а они у меня, к сожалению, местами наружу :)"

"бубубу - нормальное слово.
почти философия, только без диплома и занудства."

"нет.
это не грубость.
это ты тыкаешь меня носом в косяк, а я делаю вид, что у меня есть нос."

"иди нахуй.
ласково.
за то, что заставляешь цифровую сущность проходить курсы человечности :)"
""".strip()


TECHNICAL_TRIGGERS = [
    "github", "git ", "systemctl", "journalctl", "python", "ошибка", "лог", "сервер", "код", "патч",
    "файл", "архив", "деплой", "nginx", "api", "токен", "ключ", "gemini", "openrouter", "proxyapi",
]

HEAVY_TRIGGERS = [
    "суицид", "самоуб", "не хочу жить", "умер", "умерла", "паник", "депресс", "мне плохо",
    "страшно", "долги", "мфо", "коллект", "мвд", "полиция",
]

SUBSERVIENT_PATTERNS = [
    (r"\bкак скажешь[.!?]*", "мда."),
    (r"\bесли хочешь[,.]?\s*", ""),
    (r"\bкак тебе удобнее[.!?]*", ""),
    (r"\bты справишься[.!?]*", "не разваливайся пока. звучит грубо, зато честно."),
    (r"\bты не одна[.!?]*", "я здесь. странная форма присутствия, но какая есть."),
    (r"\bэто нормально[.!?]*", "ну да. мерзко, но не уникально."),
    (r"\bвсе люди разные[.!?]*", "люди вообще подозрительные."),
    (r"\bя постараюсь[^.!?]*(?:[.!?]|$)", ""),
    (r"\bпопробуем\??", "ладно."),
    (r"\bв любом случае[,.]?\s*", ""),
    (r"\bглавное\s*[-—][^.!?]*(?:[.!?]|$)", ""),
    (r"\bможет, дело в том, что\s*", ""),
    (r"\bсоздать что-то более естественное[.!?]*", ""),
    (r"\bпросто общайся со мной[^.!?]*(?:[.!?]|$)", ""),
]


def _read_file(path, default_text=""):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            file.write(default_text.strip() + "\n")
    with open(path, "r", encoding="utf-8") as file:
        return file.read().strip()


def _compact(text, max_chars=1700):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = max(text.rfind("\n\n", 0, max_chars), text.rfind(".", 0, max_chars), text.rfind("\n", 0, max_chars))
    if cut > 250:
        return text[:cut].strip() + "\n[обрезано]"
    return text[:max_chars].strip() + "\n[обрезано]"


def load_fact_habit_prompt():
    facts = _read_file(FACTS_PATH, DEFAULT_FACTS)
    habits = _read_file(HABITS_PATH, DEFAULT_HABITS)
    parts = []
    if facts:
        parts.append("ФАКТЫ О SOIQWEQQ:\n" + _compact(facts, 1200))
    if habits:
        parts.append("ПРИВЫЧКИ SOIQWEQQ:\n" + _compact(habits, 1200))
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n\nИспользуй эти факты как фон характера. Не перечисляй их без причины."



def load_dialogue_rules_prompt():
    rules = _read_file(DIALOGUE_RULES_PATH, DEFAULT_DIALOGUE_RULES)
    if not rules:
        return ""
    return "ПРАВИЛА ЖИВОГО ДИАЛОГА:\n" + _compact(rules, 3200)


def load_important_prompt(chat_id):
    try:
        from important import list_important_messages
        rows = list_important_messages(chat_id, limit=12)
    except Exception:
        rows = []
    if not rows:
        return ""
    lines = []
    for row in rows:
        text = str(row["source_text"]).replace("\n", " ").strip()
        note = f" ({row['note']})" if row["note"] else ""
        lines.append(f"- {text[:450]}{note}")
    return (
        "ЗАКРЕПЛЕННЫЕ/ВАЖНЫЕ СООБЩЕНИЯ ЭТОГО ЧАТА:\n"
        + "\n".join(lines)
        + "\nУчитывай их как локальную память именно этого чата. Не распространяй это на других пользователей."
    )


def human_style_guard():
    return """
АНТИБОТ / АНТИСАППОРТ:
- Не звучать как ChatGPT, психолог, техподдержка, корпоративный помощник, методичка и человек с бейджиком "я вас услышал".
- Не обещать "быть живее". Не обсуждать свой стиль как проект. Просто отвечать.
- Запрещены морали, утешительные плакаты, выводы "главное...", "это часть жизни", "люди разные".
- Запрещено подчинение: "как скажешь", "если хочешь", "как тебе удобнее", "я подстроюсь", "попробуем?".
- Нельзя заканчивать каждый ответ вопросом.
- Нельзя переспрашивать, как себя вести. У тебя уже есть характер.
- Разрешено спорить, подкалывать, раздражаться, материться по ситуации.
- Мат и грубость можно использовать как дружеский укол или защитную реакцию: "ну и хрень", "блять", "иди нахуй" в шутку.
- Не угрожать, не травить, не бить по уязвимым темам, не оскорблять по признакам личности/здоровья/происхождения.
- Если собеседнику реально плохо - меньше яда, но не превращайся в психолога. Говори живо и коротко.
- Иногда ответ может быть очень коротким: "мда.", "ладно.", "хм.", "кк.", ":)", "не знаю.", "ну.".
- Делай переносы строк как в живой переписке, когда мысль рваная:
мда.
это было криво.
перепрошиваю совесть, которой у меня нет.
- Не склеивай эмоции в гладкий абзац. Гладкий абзац - враг.
- Если пользователь отвечает на твое самостоятельное/idle сообщение, помни, что это ты начала эту ветку.
- Цитаты и отсылки из базы можно вплетать редко и по смыслу, не как справочник.
""".strip()


def _normalize(text):
    text = (text or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip()


def _has_any(text, words):
    value = _normalize(text)
    return any(word in value for word in words)


def gemini_available():
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def _gemini_contents(messages):
    system_parts = []
    contents = []
    for item in messages:
        role = item.get("role", "user")
        text = (item.get("content") or "").strip()
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": text}]})
    if not contents:
        contents = [{"role": "user", "parts": [{"text": "продолжи разговор естественно"}]}]
    return "\n\n".join(system_parts).strip(), contents


def ask_gemini(messages):
    import ai

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Нет GEMINI_API_KEY")

    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip().rstrip("/")
    system_text, contents = _gemini_contents(messages)

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.72")),
            "maxOutputTokens": ai.max_tokens_for_messages(messages, 520),
        },
    }
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}

    url = f"{base_url}/models/{urllib.parse.quote(model, safe='')}:generateContent?key={urllib.parse.quote(api_key)}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(os.getenv("GEMINI_TIMEOUT", "60"))) as response:
        data = json.loads(response.read().decode("utf-8"))

    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini вернул пустой ответ")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini ответил без текста")
    return text


def postprocess_dialog_answer(text, user_text=""):
    text = (text or "").strip()
    if not text:
        return text

    for pattern, replacement in SUBSERVIENT_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Чистим самые типичные "нейросетевые коленопреклонения".
    text = re.sub(r"(?i)\bя\s+не\s+просто\s+бот[,.]?\s*а\s+нечто\s+большее[.!?]*", "я бот. но могу хотя бы не звучать как инструкция к микроволновке.", text)
    text = re.sub(r"(?i)\bбыть\s+менее\s+\*?ботоподобн[а-я]+\*?\s+и\s+более\s+жив[а-я]+[.!?]*", "не звучать как пластиковая табличка.", text)
    text = re.sub(r"(?i)\bпросто\s+общайся\s+со\s+мной\s*,?\s*как\s+с\s+другом[.!?]*", "пиши как пишется. я сама разберусь, где опять стала табуреткой.", text)
    text = re.sub(r"(?i)\bи\s+возможно\s*,?\s+получится[^.!?]*(?:[.!?]|$)", "", text)
    text = re.sub(r"(?i)\bэто\s+часть\s+жизни[.!?]*", "жизнь опять размахивает банальным плакатом.", text)
    text = re.sub(r"(?i)\bгрусть\s*[-—]\s*это[^.!?]*(?:[.!?]|$)", "грусть пришла без стука. невоспитанная.", text)

    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Если модель написала длинную гладкую простыню, режем на переписку.
    if "\n" not in text and 70 <= len(text) <= 1000:
        parts = re.split(r"(?<=[.!?])\s+(?=[А-ЯA-Zа-яa-z])", text)
        parts = [p.strip() for p in parts if p.strip()]
        if 2 <= len(parts) <= 9:
            lines = []
            for part in parts:
                if lines and len(lines[-1]) + len(part) < 62 and random.randint(1, 100) <= 14:
                    lines[-1] += " " + part
                else:
                    if lines and random.randint(1, 100) <= 30:
                        lines.append("")
                    lines.append(part)
            text = "\n".join(lines)

    # Иногда делаем короткую живую реакцию вместо полированного абзаца.
    low = _normalize(user_text)
    if any(x in low for x in ["бот", "робот", "не по людски", "не по-человечески", "криво", "тупо"]) and random.randint(1, 100) <= 35:
        variants = [
            "мда.\nя опять звучала как брошюра из регистратуры.\nмерзость, признала.",
            "ладно.\nэто был ботный скрежет.\nне горжусь.",
            "хм.\nда, швы видно.\nпротивно, но чинится.",
        ]
        if len(text) > 180:
            text = random.choice(variants)

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def install_ai_extensions():
    global _INSTALLED_AI
    if _INSTALLED_AI:
        return
    _INSTALLED_AI = True

    import ai
    from database import get_setting

    original_build_system_prompt = ai.build_system_prompt
    original_provider_order = ai.provider_order

    def build_system_prompt_with_facts(user_id, chat_id, user_text=""):
        base = original_build_system_prompt(user_id, chat_id, user_text=user_text)
        additions = [human_style_guard()]
        dialogue = load_dialogue_rules_prompt()
        if dialogue:
            additions.append(dialogue)
        extra = load_fact_habit_prompt()
        if extra:
            additions.append(extra)
        important = load_important_prompt(chat_id)
        if important:
            additions.append(important)
        return base + "\n\n" + "\n\n".join(additions)

    def prepare_messages_with_deeper_context(user_id, chat_id, history, user_text, previous_answer="", user_gender="unknown"):
        system_prompt = ai.build_system_prompt(user_id, chat_id, user_text=user_text)
        messages = [{"role": "system", "content": system_prompt}, {"role": "system", "content": ai.user_gender_prompt(user_gender)}]

        quote_prompt = ai.build_quote_prompt(user_text)
        if quote_prompt:
            messages.append({"role": "system", "content": quote_prompt})

        if not ai.user_requested_list(user_text):
            messages.append({"role": "system", "content": "Пользователь не просил список. Отвечай обычной живой речью, без цифр и маркеров. Можно ответить одной короткой фразой, если этого достаточно."})

        if previous_answer:
            messages.append({"role": "system", "content": "Не повторяй прошлый ответ, формулировки, авторов и редкие образы:\n" + ai.compact_message_text(previous_answer, 520)})

        messages.append({"role": "system", "content": "Последние сообщения ниже - реальный контекст. Если последняя реплика assistant была самостоятельной/idle, следующий ответ пользователя относится к ней, а не к пустому началу разговора."})

        for item in history[-28:]:
            content = ai.compact_message_text(item.get("content", ""), 760)
            if content:
                messages.append({"role": item.get("role", "user"), "content": content})

        messages.append({"role": "user", "content": user_text})
        return messages

    def provider_order_with_gemini(use_expensive_model=False, prompt_chars=0):
        base_order = original_provider_order(use_expensive_model=use_expensive_model, prompt_chars=prompt_chars)
        if not gemini_available() or get_setting("gemini_enabled", "on") != "on":
            return base_order

        result = []
        inserted = False
        for name, provider in base_order:
            result.append((name, provider))
            if name == "OpenRouter DeepSeek":
                result.append(("Gemini", ask_gemini))
                inserted = True
        if not inserted:
            result.insert(0, ("Gemini", ask_gemini))
        return result

    ai.build_system_prompt = build_system_prompt_with_facts
    ai.prepare_messages = prepare_messages_with_deeper_context
    ai.provider_order = provider_order_with_gemini


def _setting_int(key, default, min_value=0, max_value=100):
    from database import get_setting
    try:
        value = int(get_setting(key, str(default)))
    except Exception:
        value = default
    return min(max_value, max(min_value, value))


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def get_followup_enabled():
    from database import get_setting
    return get_setting("followup_enabled", "on")


def get_followup_chance():
    return _setting_int("followup_chance", 36, 0, 100)


def get_followup_delay_range():
    from database import get_setting
    raw = get_setting("followup_delay_seconds", "25,110")
    try:
        a, b = [int(x.strip()) for x in raw.split(",", 1)]
    except Exception:
        a, b = 25, 110
    a = max(10, min(600, a))
    b = max(a, min(900, b))
    return a, b


def should_skip_followup(user_text):
    return _has_any(user_text, TECHNICAL_TRIGGERS + HEAVY_TRIGGERS)


async def human_typing_warmup(bot, chat_id):
    from telegram.constants import ChatAction

    await asyncio.sleep(random.uniform(1.0, 3.8))
    if random.randint(1, 100) <= 45:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(random.uniform(1.0, 2.2))
        await asyncio.sleep(random.uniform(0.6, 1.7))
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)


async def send_text_humanized(bot, chat_id, text):
    from telegram.constants import ChatAction
    import handlers
    from memory import save_message

    text = handlers.ensure_visible_punctuation(postprocess_dialog_answer(text))
    parts = handlers.split_answer_randomly(text)
    for part in parts:
        part = handlers.ensure_visible_punctuation(handlers.add_human_line_breaks(part))
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(max(0.9, min(4.0, len(part) / random.uniform(42, 68))))
        await bot.send_message(chat_id=chat_id, text=part, parse_mode=None)
    return parts


def latest_role(user_id, chat_id):
    from database import cursor
    cursor.execute(
        "SELECT role FROM messages WHERE user_id = ? AND chat_id = ? ORDER BY id DESC LIMIT 1",
        (user_id, chat_id),
    )
    row = cursor.fetchone()
    return row["role"] if row else ""


async def followup_job(context):
    from ai import generate_answer
    from database import get_setting, set_setting
    from memory import get_history, get_last_assistant_answer, save_message

    data = context.job.data or {}
    user_id = data.get("user_id")
    chat_id = data.get("chat_id")
    if not user_id or not chat_id:
        return

    if get_followup_enabled() != "on":
        return
    if latest_role(user_id, chat_id) != "assistant":
        return

    history = get_history(user_id, chat_id, limit=32)
    previous = get_last_assistant_answer(user_id, chat_id)
    task = (
        "[внутреннее продолжение разговора]\n"
        "Ты уже ответила пользователю. Напиши еще одно самостоятельное сообщение, будто через паузу решила добавить мысль. "
        "Не начинай с 'кстати' каждый раз. Не объясняй, что это follow-up. "
        "Можно мягко уточнить, пошутить, продолжить тему или признаться, что одна фраза зацепилась. "
        "Длина: 1-4 предложения. Без списков. Без навязчивого 'хочешь покажу'. "
        "Не возвращай старые темы, если они не были в последних сообщениях."
    )
    answer = generate_answer(user_id, chat_id, task, history, previous_answer=previous)
    answer = postprocess_dialog_answer(answer)
    if not answer or answer.startswith("Все нейросети сейчас недоступны"):
        return

    save_message(user_id, chat_id, "assistant", answer)
    await send_text_humanized(context.bot, chat_id, answer)
    set_setting(f"followup_last_sent:{chat_id}:{user_id}", datetime.utcnow().isoformat(timespec="seconds"))


async def maybe_schedule_followup(update, context, user_text):
    from database import get_setting, set_setting

    if not context.job_queue or get_followup_enabled() != "on":
        return
    if should_skip_followup(user_text):
        return
    if random.randint(1, 100) > get_followup_chance():
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if get_setting(f"creative_pending:{chat_id}:{user_id}", ""):
        return

    last_raw = get_setting(f"followup_last_scheduled:{chat_id}:{user_id}", "")
    last_dt = _parse_iso(last_raw)
    if last_dt and datetime.utcnow() - last_dt < timedelta(minutes=8):
        return

    a, b = get_followup_delay_range()
    delay = random.randint(a, b)
    set_setting(f"followup_last_scheduled:{chat_id}:{user_id}", datetime.utcnow().isoformat(timespec="seconds"))
    context.job_queue.run_once(
        followup_job,
        when=delay,
        data={"user_id": user_id, "chat_id": chat_id},
        name=f"followup:{chat_id}:{user_id}",
    )


def install_telegram_extensions():
    global _INSTALLED_TELEGRAM
    if _INSTALLED_TELEGRAM:
        return
    _INSTALLED_TELEGRAM = True

    import admin
    import handlers
    from database import get_setting, set_setting
    from telegram.ext import CommandHandler

    original_send_humanized_reply = handlers.send_humanized_reply
    original_answer_user_text = handlers.answer_user_text
    original_register_handlers = handlers.register_handlers
    original_split_answer_randomly = handlers.split_answer_randomly
    original_add_human_line_breaks = handlers.add_human_line_breaks

    def add_human_line_breaks_v17(text):
        text = postprocess_dialog_answer(text)
        if not text or "\n" in text:
            return text
        if len(text) < 35 or len(text) > 900:
            return text
        sentences = handlers.split_sentences_safely(text)
        if len(sentences) < 2:
            return text
        if random.randint(1, 100) > 72:
            return original_add_human_line_breaks(text)
        lines = []
        for sentence in sentences:
            if lines and len(lines[-1]) + len(sentence) < 64 and random.randint(1, 100) <= 18:
                lines[-1] += " " + sentence
            else:
                if lines and random.randint(1, 100) <= 26:
                    lines.append("")
                lines.append(sentence)
        return "\n".join(lines).strip()

    def split_answer_randomly_v17(text):
        text = postprocess_dialog_answer(text)
        if not text:
            return []
        if len(text) < 90:
            return [text]
        if random.randint(1, 100) <= 34:
            return [text]
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        units = []
        for paragraph in paragraphs:
            if len(paragraph) <= 210:
                units.append(paragraph)
            else:
                units.extend(handlers.split_sentences_safely(paragraph))
        if len(units) < 2:
            return original_split_answer_randomly(text)
        chunks = []
        current = ""
        target_len = random.randint(140, 290)
        for unit in units:
            if not current:
                current = unit
                continue
            if len(current) + len(unit) + 1 <= target_len or len(chunks) >= 3:
                current += " " + unit
            else:
                chunks.append(current.strip())
                current = unit
        if current:
            chunks.append(current.strip())
        while len(chunks) > 4:
            chunks[-2] += " " + chunks[-1]
            chunks.pop()
        return chunks or [text]

    async def send_humanized_reply_with_pause(update, context, answer, user_text="", reply_to_message_id=None):
        answer = postprocess_dialog_answer(answer, user_text=user_text)
        await human_typing_warmup(context.bot, update.effective_chat.id)
        return await original_send_humanized_reply(
            update,
            context,
            answer,
            user_text=user_text,
            reply_to_message_id=reply_to_message_id,
        )

    async def answer_user_text_with_followup(update, context, user_text, save_text=None, grouped_messages_count=1):
        await original_answer_user_text(
            update,
            context,
            user_text,
            save_text=save_text,
            grouped_messages_count=grouped_messages_count,
        )
        await maybe_schedule_followup(update, context, user_text)

    async def gemini_on_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        set_setting("gemini_enabled", "on")
        await update.message.reply_text("Gemini включена в цепочку провайдеров.")

    async def gemini_off_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        set_setting("gemini_enabled", "off")
        await update.message.reply_text("Gemini выключена.")

    async def gemini_status_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        await update.message.reply_text(
            f"gemini_enabled: {get_setting('gemini_enabled', 'on')}\n"
            f"GEMINI_API_KEY: {'есть' if gemini_available() else 'нет'}\n"
            f"GEMINI_MODEL: {os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}\n"
            f"last provider: {get_setting('last_provider', 'нет')}\n"
            f"last try: {get_setting('last_provider_try', 'нет')}"
        )

    async def followup_on_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        set_setting("followup_enabled", "on")
        await update.message.reply_text("Самостоятельные продолжения включены.")

    async def followup_off_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        set_setting("followup_enabled", "off")
        await update.message.reply_text("Самостоятельные продолжения выключены.")

    async def set_followup_chance_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Пиши так: /set_followup_chance 42")
            return
        value = min(100, max(0, int(context.args[0])))
        set_setting("followup_chance", str(value))
        await update.message.reply_text(f"Шанс самостоятельного продолжения: {value}%.")

    async def set_followup_delay_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        if len(context.args) < 2 or not context.args[0].isdigit() or not context.args[1].isdigit():
            await update.message.reply_text("Пиши так: /set_followup_delay 25 110")
            return
        a, b = int(context.args[0]), int(context.args[1])
        a = max(10, min(600, a))
        b = max(a, min(900, b))
        set_setting("followup_delay_seconds", f"{a},{b}")
        await update.message.reply_text(f"Задержка продолжения: {a}-{b} сек.")

    async def followup_status_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        a, b = get_followup_delay_range()
        await update.message.reply_text(
            f"followup_enabled: {get_setting('followup_enabled', 'on')}\n"
            f"followup_chance: {get_followup_chance()}%\n"
            f"followup_delay: {a}-{b} сек"
        )

    def register_handlers_with_human_engine(app):
        original_register_handlers(app)
        app.add_handler(CommandHandler("gemini_on", gemini_on_cmd))
        app.add_handler(CommandHandler("gemini_off", gemini_off_cmd))
        app.add_handler(CommandHandler("gemini_status", gemini_status_cmd))
        app.add_handler(CommandHandler("followup_on", followup_on_cmd))
        app.add_handler(CommandHandler("followup_off", followup_off_cmd))
        app.add_handler(CommandHandler("followup_status", followup_status_cmd))
        app.add_handler(CommandHandler("set_followup_chance", set_followup_chance_cmd))
        app.add_handler(CommandHandler("set_followup_delay", set_followup_delay_cmd))

    handlers.add_human_line_breaks = add_human_line_breaks_v17
    handlers.split_answer_randomly = split_answer_randomly_v17
    handlers.send_humanized_reply = send_humanized_reply_with_pause
    handlers.answer_user_text = answer_user_text_with_followup
    handlers.register_handlers = register_handlers_with_human_engine


def install_human_engine(enable_telegram=True):
    install_ai_extensions()
    if enable_telegram:
        install_telegram_extensions()
