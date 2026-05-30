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

TECHNICAL_TRIGGERS = [
    "github", "git ", "systemctl", "journalctl", "python", "ошибка", "лог", "сервер", "код", "патч",
    "файл", "архив", "деплой", "nginx", "api", "токен", "ключ", "gemini", "openrouter", "proxyapi",
]

HEAVY_TRIGGERS = [
    "суицид", "самоуб", "не хочу жить", "умер", "умерла", "паник", "депресс", "мне плохо",
    "страшно", "долги", "мфо", "коллект", "мвд", "полиция",
]

CREATIVE_FRIENDLY_TRIGGERS = [
    "ночь", "сон", "скучно", "тишина", "странно", "музыка", "плейлист", "город", "кот", "история",
    "стих", "творч", "грустно", "пусто", "красиво", "атмосфер", "зарисов", "рассказ",
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


def _normalize(text):
    text = (text or "").lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip()


def _has_any(text, words):
    value = _normalize(text)
    return any(word in value for word in words)


def _env_bool(name, default="on"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on", "да"}


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
            "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.65")),
            "maxOutputTokens": ai.max_tokens_for_messages(messages, 430),
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
        extra = load_fact_habit_prompt()
        if extra:
            base += "\n\n" + extra
        return base

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
    return _setting_int("followup_chance", 24, 0, 100)


def get_followup_delay_range():
    from database import get_setting
    raw = get_setting("followup_delay_seconds", "35,150")
    try:
        a, b = [int(x.strip()) for x in raw.split(",", 1)]
    except Exception:
        a, b = 35, 150
    a = max(10, min(600, a))
    b = max(a, min(900, b))
    return a, b


def should_skip_followup(user_text):
    return _has_any(user_text, TECHNICAL_TRIGGERS + HEAVY_TRIGGERS)


async def human_typing_warmup(bot, chat_id):
    from telegram.constants import ChatAction

    await asyncio.sleep(random.uniform(0.8, 2.8))
    if random.randint(1, 100) <= 42:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        # Пауза без typing - выглядит как "написала, стерла, задумалась".
        await asyncio.sleep(random.uniform(0.6, 1.6))
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)


async def send_text_humanized(bot, chat_id, text):
    from telegram.constants import ChatAction
    import handlers
    from memory import save_message

    text = handlers.ensure_visible_punctuation(text)
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
        # Пользователь уже ответил сам. Не лезем между репликами, мы же не дверной скрип.
        return

    history = get_history(user_id, chat_id)
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

    # Если висит творческое предложение, не мешаем ему вторым самостоятельным сообщением.
    if get_setting(f"creative_pending:{chat_id}:{user_id}", ""):
        return

    last_raw = get_setting(f"followup_last_scheduled:{chat_id}:{user_id}", "")
    last_dt = _parse_iso(last_raw)
    if last_dt and datetime.utcnow() - last_dt < timedelta(minutes=18):
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

    async def send_humanized_reply_with_pause(update, context, answer, user_text="", reply_to_message_id=None):
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
        await update.message.reply_text("Gemini выключена. Еще один бог API отправлен в угол.")

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
            await update.message.reply_text("Пиши так: /set_followup_chance 24")
            return
        value = min(100, max(0, int(context.args[0])))
        set_setting("followup_chance", str(value))
        await update.message.reply_text(f"Шанс самостоятельного продолжения: {value}%.")

    async def set_followup_delay_cmd(update, context):
        if not admin.is_admin(update):
            await update.message.reply_text("Нет доступа.")
            return
        if len(context.args) < 2 or not context.args[0].isdigit() or not context.args[1].isdigit():
            await update.message.reply_text("Пиши так: /set_followup_delay 35 150")
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

    handlers.send_humanized_reply = send_humanized_reply_with_pause
    handlers.answer_user_text = answer_user_text_with_followup
    handlers.register_handlers = register_handlers_with_human_engine


def install_human_engine(enable_telegram=True):
    install_ai_extensions()
    if enable_telegram:
        install_telegram_extensions()
