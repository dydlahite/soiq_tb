import random
import re
import asyncio
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

import admin
from ai import generate_answer
from database import get_setting, set_setting
from important import (
    add_important_message,
    list_important_messages,
    delete_important_message,
    clear_important_messages,
)
from forbidden import clean_forbidden_phrases
from memory import save_message, get_history, get_last_assistant_answer
from moods import get_current_mood
from media import maybe_send_media, clear_media, clear_media_seen, get_random_media, send_media_item
from idle import touch_chat, schedule_idle_jobs, send_idle_now
from channel import (
    schedule_channel_jobs,
    channel_status_text,
    set_channel_enabled,
    set_channel_id,
    set_channel_hours,
    set_channel_chance,
    set_channel_mode,
    set_channel_format,
    send_channel_post,
    clear_channel_recent,
)
from multimodal import (
    transcribe_audio_file,
    describe_image_file,
    set_voice_input,
    set_image_input,
    get_voice_input,
    get_image_input,
)
from quotes import (
    quote_status_text,
    set_quote_chance,
    get_quote_chance,
    set_quote_match_threshold,
    get_quote_match_threshold,
    ensure_quote_file,
)
from tts import (
    should_send_voice,
    make_tts_file,
    cleanup_voice_file,
    record_voice_sent,
    set_tts_voice,
    set_tts_model,
    get_tts_voice,
    get_tts_model,
    SUPPORTED_TTS_VOICES,
)


PROVIDER_FAILURE_PREFIX = "Все нейросети сейчас недоступны"
TEST_VOICE_TEXT = "проверка голоса. звучит терпимо или опять как лифт в поликлинике."
MAX_REPLY_PARTS = 4
SHORT_BARE_REPLIES = {
    "да", "нет", "хм", "мда", "ну", "ок", "кк", "окак", "ага", "угу", "неа", "ладно",
    "приняла", "поняла", "ясно", "бывает", "увы", "что ж", "пожалуй",
}



SHORT_REACTION_WORDS = {
    "хм", "мда", "да", "нет", "ну", "кк", "ок", "окак", "ладно",
    "поняла", "ясно", "угу", "ага", "эх", "увы"
}


def is_short_reaction_line(line):
    value = (line or "").strip().lower().replace("ё", "е")
    value = re.sub(r"[.!?…]+$", "", value).strip()
    return value in SHORT_REACTION_WORDS


def fix_short_reaction_punctuation(text):
    if not text:
        return text

    lines = text.splitlines()
    fixed = []

    for line in lines:
        stripped = line.rstrip()

        if not stripped:
            fixed.append(stripped)
            continue

        if is_short_reaction_line(stripped):
            fixed.append(re.sub(r"[.!?…]+$", "", stripped).rstrip() + ".")
        else:
            fixed.append(stripped)

    return "\n".join(fixed).strip()


def is_short_bare_reply(line):
    return line.strip().lower().replace(".", "") in SHORT_BARE_REPLIES
REACTION_RULES_PATH = "reaction_rules.txt"
PENDING_TEXT_BUFFERS = {}



def setting_int(key, default, min_value=0, max_value=100):
    try:
        value = int(get_setting(key, str(default)))
    except (TypeError, ValueError):
        value = default

    return min(max_value, max(min_value, value))


def get_message_buffer_mode():
    return get_setting("message_buffer", "on")


def get_message_buffer_seconds():
    return setting_int("message_buffer_seconds", 6, min_value=1, max_value=30)


def get_reply_mode():
    return get_setting("reply_mode", "random")


def get_reply_chance():
    return setting_int("reply_chance", 18, min_value=0, max_value=100)


def set_last_bot_message(chat_id, message_id):
    if chat_id and message_id:
        set_setting(f"last_bot_message_id:{chat_id}", str(message_id))


def get_last_bot_message(chat_id):
    raw = get_setting(f"last_bot_message_id:{chat_id}", "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def message_preview(message):
    if not message:
        return ""

    text = message.text or message.caption or ""
    if text:
        return text.strip()[:900]

    if message.photo:
        return "[фото без подписи]"
    if message.voice:
        return "[голосовое сообщение]"
    if message.sticker:
        return "[стикер]"
    if message.animation:
        return "[gif/animation]"
    if message.video:
        return "[видео]"
    if message.document:
        return f"[файл: {message.document.file_name or 'без названия'}]"

    return "[сообщение без текста]"


def build_reply_context_text(update: Update, user_text: str):
    replied = update.message.reply_to_message if update.message else None

    if not replied:
        return user_text

    quoted_text = message_preview(replied)
    if not quoted_text:
        return user_text

    author = "собеседника"
    if replied.from_user:
        author = replied.from_user.full_name or "собеседника"

    return (
        "[контекст Telegram-ответа]\n"
        f"Пользователь отвечает на сообщение от {author}:\n"
        f"{quoted_text}\n\n"
        "[новое сообщение пользователя]\n"
        f"{user_text}"
    )


def choose_reply_to_message_id(update: Update, grouped_messages_count=1):
    if not update.message:
        return None

    mode = get_reply_mode()

    if mode == "off":
        return None

    if mode == "on":
        return update.message.message_id

    # random: не цитируем каждое сообщение, а только когда это выглядит уместно.
    chance = get_reply_chance()

    if update.message.reply_to_message:
        chance = max(chance, 70)
    elif grouped_messages_count and grouped_messages_count > 1:
        chance = max(chance, 30)

    if random.randint(1, 100) <= chance:
        return update.message.message_id

    return None


def make_grouped_user_text(items):
    if len(items) <= 1:
        return items[0]["ai_text"]

    lines = ["[пользователь отправил несколько сообщений подряд]"]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item['ai_text']}")

    return "\n".join(lines)


def make_grouped_save_text(items):
    if len(items) <= 1:
        return items[0]["raw_text"]

    return "\n".join(item["raw_text"] for item in items)



def is_provider_failure_answer(answer):
    return bool(answer and answer.strip().startswith(PROVIDER_FAILURE_PREFIX))


def split_sentences_safely(text):
    parts = re.split(r"(?<!\b\d)(?<=[.!?])\s+(?=[А-ЯA-Zа-яa-z])", text.strip())
    return [part.strip() for part in parts if part.strip()]




def normalize_visible_smileys(text):
    if not text:
        return text

    text = text.replace("* .. :) *", ".. :)")
    text = re.sub(r"\*+\s*\.\.\s*:\)\s*\*+", ".. :)", text)
    text = re.sub(r"\.{2,}\s*\)+", ".. :)", text)
    text = re.sub(r"\.\.\s*:\)", ".. :)", text)
    text = re.sub(r"(:\)|\.\.\s*:\))\s*[.)]+(?=\s*($|\n))", r"\1", text)
    text = re.sub(r"\.\.\s*:\)\s*\.+", ".. :)", text)
    text = re.sub(r":\)\s*\.+(?=\s*($|\n))", ":)", text)
    return text


def normalize_visible_stray_punctuation(text):
    if not text:
        return text

    fixed = []

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            fixed.append(stripped)
            continue

        if stripped.endswith(".. :)") or stripped.endswith(":)"):
            fixed.append(stripped)
            continue

        # Убираем случайную ведущую пунктуацию: ". что дальше?" -> "что дальше?".
        stripped = re.sub(r"^[\s,.;:!?]+(?=[А-Яа-яA-Za-z0-9])", "", stripped)

        # Убираем кривые хвосты: "что дальше?)." -> "что дальше?".
        stripped = re.sub(r"\?\)+\s*\.*$", "?", stripped)
        stripped = re.sub(r"!\)+\s*\.*$", "!", stripped)
        stripped = re.sub(r"\.\)+\s*$", ".", stripped)

        if "(" not in stripped and not stripped.endswith(":)") and not stripped.endswith(".. :)"):
            stripped = re.sub(r"\)+(?=\s*$)", "", stripped).rstrip()

        stripped = re.sub(r"\?\s*\.+$", "?", stripped)
        stripped = re.sub(r"!\s*\.+$", "!", stripped)
        stripped = re.sub(r",\s*\.+$", ".", stripped)
        stripped = re.sub(r"\s+([,.!?;:])", r"\1", stripped)

        fixed.append(stripped)

    return fix_short_reaction_punctuation("\n".join(fixed).strip())


def ensure_visible_punctuation(text):
    if not text:
        return text

    text = normalize_visible_smileys(text)
    text = normalize_visible_stray_punctuation(text)
    lines = text.splitlines()
    nonempty_lines = [line.strip() for line in lines if line.strip()]
    only_short_bare_reply = len(nonempty_lines) == 1 and is_short_bare_reply(nonempty_lines[0])
    fixed = []

    for line in lines:
        stripped = line.rstrip()

        if not stripped:
            fixed.append(stripped)
            continue

        if stripped.endswith(".. :)") or stripped.endswith(":)"):
            fixed.append(stripped)
            continue

        # Если "хм"/"ну"/"кк" - весь ответ, оставляем голым.
        # Если после него идет еще текст, ставим точку: это уже отдельное предложение.
        if is_short_bare_reply(stripped):
            stripped = stripped.rstrip(".!?")
            if not only_short_bare_reply:
                stripped += "."
            fixed.append(stripped)
            continue

        if stripped[-1] not in ".!?":
            stripped += "."

        fixed.append(stripped)

    return normalize_visible_stray_punctuation(normalize_visible_smileys("\n".join(fixed).strip()))


def add_human_line_breaks(text):
    if not text or "\n" in text:
        return text

    if len(text) < 55 or len(text) > 620:
        return text

    if random.randint(1, 100) > 58:
        return text

    sentences = split_sentences_safely(text)

    if len(sentences) < 2 or len(sentences) > 6:
        return text

    lines = []

    for sentence in sentences:
        if lines and len(lines[-1]) + len(sentence) < 58 and random.randint(1, 100) <= 22:
            lines[-1] += " " + sentence
        else:
            if lines and random.randint(1, 100) <= 26:
                lines.append("")
            lines.append(sentence)

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    if cleaned.count("\n") < 1:
        return text

    return cleaned


def split_answer_randomly(text):
    if not text:
        return []

    text = text.strip()

    if len(text) < 240 or random.randint(1, 100) <= 55:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    units = []

    for paragraph in paragraphs:
        if len(paragraph) <= 260:
            units.append(paragraph)
        else:
            units.extend(split_sentences_safely(paragraph))

    if len(units) < 2:
        return [text]

    target_len = random.randint(230, 430)
    chunks = []
    current = ""

    for unit in units:
        if not current:
            current = unit
            continue

        if len(current) + len(unit) + 1 <= target_len or len(chunks) >= MAX_REPLY_PARTS - 1:
            current += " " + unit
        else:
            chunks.append(current.strip())
            current = unit

    if current:
        chunks.append(current.strip())

    while len(chunks) > MAX_REPLY_PARTS:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()

    return chunks


def get_reaction_chance():
    try:
        return min(100, max(0, int(get_setting("reaction_chance", "12"))))
    except ValueError:
        return 12


DEFAULT_REACTION_RULES = """
# Формат: эмодзи | ключевые слова через запятую | заметка для себя
# Бот ставит реакцию только если нашел ключевые слова. Случайной реакции без причины больше нет.

💔 | грустно, больно, плохо, пусто, печально, устала, плачу, тяжело | когда собеседнику плохо или в ответе тоскливо
😔 | печально, жалко, жаль, тоскливо, грусть, усталость | мягкая грусть без драматического сердца
🖤 | романтично, нежно, люблю, скучаю, ночь, мягко, тепло | теплая/романтичная окраска
😏 | ахах, хаха, смешно, ну да, конечно, ирония, сарказм | ирония и смешки
👌 | спасибо, поняла, хорошо, ок, принято, супер, отлично | подтверждение и спокойное принятие
👀 | странно, интересно, что, как, почему, внезапно, подозрительно | любопытство или странность
""".strip()


def ensure_reaction_rules_file():
    try:
        with open(REACTION_RULES_PATH, "x", encoding="utf-8") as file:
            file.write(DEFAULT_REACTION_RULES + "\n")
    except FileExistsError:
        pass


def load_reaction_rules():
    ensure_reaction_rules_file()

    rules = []

    with open(REACTION_RULES_PATH, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            parts = [part.strip() for part in line.split("|", 2)]

            if len(parts) < 2:
                continue

            emoji = parts[0]
            triggers = [item.strip().lower() for item in parts[1].split(",") if item.strip()]

            if emoji and triggers:
                rules.append((emoji, triggers))

    return rules


def choose_reaction(user_text, answer):
    text_l = ((user_text or "") + "\n" + (answer or "")).lower()
    candidates = []

    for emoji, triggers in load_reaction_rules():
        if any(trigger in text_l for trigger in triggers):
            candidates.append(emoji)

    if not candidates:
        return None

    return random.choice(candidates)


async def maybe_react_to_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, answer: str):
    if get_setting("reactions", "on") != "on":
        return

    if random.randint(1, 100) > get_reaction_chance():
        return

    try:
        from telegram import ReactionTypeEmoji

        emoji = choose_reaction(user_text, answer)

        if not emoji:
            return

        await context.bot.set_message_reaction(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)],
            is_big=False,
        )
    except Exception as error:
        print("reaction failed:")
        print(error)


async def send_voice_file(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, voice_override=None, model_override=None, reply_to_message_id=None):
    voice_path = None

    try:
        voice_path, is_voice = make_tts_file(
            text,
            voice_override=voice_override,
            model_override=model_override,
        )

        with open(voice_path, "rb") as file:
            if is_voice:
                sent = await context.bot.send_voice(
                    chat_id=update.effective_chat.id,
                    voice=file,
                    reply_to_message_id=reply_to_message_id,
                )
            else:
                sent = await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=file,
                    reply_to_message_id=reply_to_message_id,
                )

        set_last_bot_message(update.effective_chat.id, sent.message_id)
        return True

    except Exception as error:
        print("TTS failed:")
        print(error)
        sent = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Голос {voice_override or get_tts_voice()} не вышел. Провайдер снова устроил цирк в серверной.",
            reply_to_message_id=reply_to_message_id,
        )
        set_last_bot_message(update.effective_chat.id, sent.message_id)
        return False

    finally:
        cleanup_voice_file(voice_path)

async def send_voice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str, reply_to_message_id=None):
    ok = await send_voice_file(update, context, answer, reply_to_message_id=reply_to_message_id)

    if ok:
        record_voice_sent()

    return ok


async def send_humanized_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str, user_text: str = "", reply_to_message_id=None):
    answer = ensure_visible_punctuation(answer)

    if should_send_voice(answer, user_text=user_text, mood=get_current_mood()):
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.RECORD_VOICE,
        )

        if await send_voice_reply(update, context, answer, reply_to_message_id=reply_to_message_id):
            return

    parts = split_answer_randomly(answer)

    for index, part in enumerate(parts):
        part = ensure_visible_punctuation(add_human_line_breaks(part))

        delay = len(part) / random.uniform(45, 75)
        delay += random.uniform(0.3, 1.0)

        if index == 0:
            delay = min(delay, 2.2)
        else:
            delay = min(delay, 3.0)

        delay = max(0.35, delay)

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )

        await asyncio.sleep(delay)
        sent = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=part,
            parse_mode=None,
            reply_to_message_id=reply_to_message_id if index == 0 else None,
        )
        set_last_bot_message(update.effective_chat.id, sent.message_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and update.effective_chat:
        touch_chat(update.effective_user.id, update.effective_chat.id)

    await update.message.reply_text(
        "Qq.\nПозвони, как напишешь.\nВпрочем, интереса отвечать тебе все еще нет.\n:)",
        parse_mode=None,
    )


async def idle_now_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await send_idle_now(context.bot, update.effective_chat.id)


async def reactions_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("reactions", "on")
    await update.message.reply_text("Реакции включены.")


async def reactions_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("reactions", "off")
    await update.message.reply_text("Реакции выключены.")


async def set_reaction_chance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_reaction_chance 12")
        return

    chance = min(100, max(0, int(context.args[0])))
    set_setting("reaction_chance", str(chance))
    await update.message.reply_text(f"Шанс реакции: {chance}%.")


async def reactions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    rules_text = DEFAULT_REACTION_RULES

    try:
        ensure_reaction_rules_file()
        with open(REACTION_RULES_PATH, "r", encoding="utf-8") as file:
            rules_text = file.read().strip()
    except Exception:
        pass

    await update.message.reply_text(
        f"Реакции: {get_setting('reactions', 'on')}\n"
        f"Шанс: {get_reaction_chance()}%\n\n"
        f"Правила в файле {REACTION_RULES_PATH}:\n\n"
        f"{rules_text[:3000]}"
    )



async def quotes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    ensure_quote_file()
    await update.message.reply_text(quote_status_text())


async def set_quote_chance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_quote_chance 18")
        return

    set_quote_chance(context.args[0])
    await update.message.reply_text(f"Шанс случайного упоминания цитат: {get_quote_chance()}%.")


async def set_quote_match_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Пиши так: /set_quote_match 0.78")
        return

    set_quote_match_threshold(context.args[0])
    await update.message.reply_text(f"Порог узнавания цитат: {get_quote_match_threshold()}.")


async def reload_quotes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    ensure_quote_file()
    await update.message.reply_text("Файл quote_triggers.txt на месте. Он читается при каждом ответе, так что рестарт ради него не обязателен. Какая редкая милость.")


async def paid_fallback_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("paid_fallback", "on")
    await update.message.reply_text("Платный аварийный резерв включен. ProxyAPI сможет спасать даже обычные ответы.")


async def paid_fallback_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("paid_fallback", "off")
    await update.message.reply_text("Платный аварийный резерв выключен. Обычные ответы не будут спасаться ProxyAPI.")


async def paid_complex_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("paid_complex", "on")
    await update.message.reply_text("Намеренный платный режим включен. ProxyAPI OpenAI сможет включаться для реально технически сложных запросов.")


async def paid_complex_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("paid_complex", "off")
    await update.message.reply_text("Намеренный платный режим выключен. В дебаге ProxyAPI должен появляться только как Emergency.")


async def paid_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(
        f"paid_fallback: {get_setting('paid_fallback', 'on')}\n"
        f"paid_complex: {get_setting('paid_complex', 'off')}\n"
        f"last provider: {get_setting('last_provider', 'нет')}\n"
        f"last try: {get_setting('last_provider_try', 'нет')}\n"
        f"last complex: {get_setting('last_complex_message', 'нет')}\n"
        f"last paid complex: {get_setting('last_paid_complex', 'нет')}\n"
        f"last use expensive: {get_setting('last_use_expensive_model', 'нет')}\n"
        f"last prompt chars: {get_setting('last_prompt_chars', 'нет')}"
    )


async def groq_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("groq_enabled", "on")
    await update.message.reply_text("Groq включен. Если он снова начнет 429, это будет не баг, а очередная демонстрация хрупкости мира.")


async def groq_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("groq_enabled", "off")
    await update.message.reply_text("Groq выключен. Бот будет скипать его полностью.")


async def groq_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(
        f"groq_enabled: {get_setting('groq_enabled', 'off')}\n"
        f"last provider: {get_setting('last_provider', 'нет')}\n"
        f"last try: {get_setting('last_provider_try', 'нет')}"
    )


async def voice_input_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_voice_input(True)
    await update.message.reply_text("Распознавание входящих голосовых включено. Теперь у нас еще и уши, трагедия прогресса.")


async def voice_input_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_voice_input(False)
    await update.message.reply_text("Распознавание входящих голосовых выключено.")


async def vision_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_image_input(True)
    await update.message.reply_text("Распознавание картинок включено. Любая картинка теперь может стоить денег, потому что реальность решила быть платной.")


async def vision_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_image_input(False)
    await update.message.reply_text("Распознавание картинок выключено.")


async def multimodal_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(
        f"voice input: {get_voice_input()}\n"
        f"image input: {get_image_input()}\n"
        f"provider: {get_setting('multimodal_provider', 'proxyapi')}\n"
        f"last multimodal provider: {get_setting('last_multimodal_provider', 'нет')}\n"
        f"stt model: {get_setting('stt_model', 'whisper-1')}\n"
        f"vision model: {get_setting('vision_model', 'gpt-4o-mini')}"
    )


async def message_buffer_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("message_buffer", "on")
    await update.message.reply_text("Буфер сообщений включен. Теперь она немного подождет, прежде чем отвечать на обрывок мысли.")


async def message_buffer_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("message_buffer", "off")
    await update.message.reply_text("Буфер сообщений выключен. Будет отвечать на каждое сообщение отдельно, как нервная кофемолка.")


async def set_message_buffer_seconds_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_buffer_seconds 6")
        return

    value = min(30, max(1, int(context.args[0])))
    set_setting("message_buffer_seconds", str(value))
    await update.message.reply_text(f"Пауза буфера сообщений: {value} сек.")


async def message_buffer_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(
        f"message_buffer: {get_message_buffer_mode()}\n"
        f"buffer seconds: {get_message_buffer_seconds()}\n"
        f"pending buffers: {len(PENDING_TEXT_BUFFERS)}"
    )


async def reply_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("reply_mode", "on")
    await update.message.reply_text("Reply включен всегда. Странновато, но приказ есть приказ.")


async def reply_random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("reply_mode", "random")
    await update.message.reply_text("Reply random включен. Будет отвечать цитированием иногда, а не как липучка на каждую реплику.")


async def reply_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("reply_mode", "off")
    await update.message.reply_text("Reply выключен. Будет писать просто в чат.")


async def set_reply_chance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_reply_chance 18")
        return

    value = min(100, max(0, int(context.args[0])))
    set_setting("reply_chance", str(value))
    await update.message.reply_text(f"Шанс reply: {value}%.")


async def reply_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(
        f"reply_mode: {get_reply_mode()}\n"
        f"reply_chance: {get_reply_chance()}%\n"
        f"last bot message id: {get_last_bot_message(update.effective_chat.id) or 'нет'}"
    )


async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    target = update.message.reply_to_message
    if not target:
        await update.message.reply_text("Пиши /pin ответом на сообщение, которое надо закрепить.")
        return

    try:
        await context.bot.pin_chat_message(
            chat_id=update.effective_chat.id,
            message_id=target.message_id,
            disable_notification=True,
        )
        await update.message.reply_text("Закрепила. Маленький гвоздь в стену чата.")
    except Exception as error:
        print("pin failed:")
        print(error)
        await update.message.reply_text("Не смогла закрепить. В группе мне нужны права админа на закрепы, вот этот прекрасный бюрократический цветок.")


async def pin_last_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    message_id = get_last_bot_message(update.effective_chat.id)
    if not message_id:
        await update.message.reply_text("Не вижу последнего сообщения бота для закрепа.")
        return

    try:
        await context.bot.pin_chat_message(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            disable_notification=True,
        )
        await update.message.reply_text("Последнее сообщение бота закреплено.")
    except Exception as error:
        print("pin_last failed:")
        print(error)
        await update.message.reply_text("Не смогла закрепить последнее сообщение. Опять права, админка и прочий человеческий феодализм.")


async def unpin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    try:
        target = update.message.reply_to_message
        await context.bot.unpin_chat_message(
            chat_id=update.effective_chat.id,
            message_id=target.message_id if target else None,
        )
        await update.message.reply_text("Открепила.")
    except Exception as error:
        print("unpin failed:")
        print(error)
        await update.message.reply_text("Не смогла открепить. Видимо, чат опять держит оборону.")


async def important_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    target = update.message.reply_to_message
    if not target:
        await update.message.reply_text("Пиши /important ответом на сообщение, которое надо сохранить как важное.")
        return

    note = " ".join(context.args).strip() or None
    source_text = message_preview(target)
    item_id = add_important_message(
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
        message_id=target.message_id,
        source_text=source_text,
        note=note,
    )
    await update.message.reply_text(f"Сохранила как важное #{item_id}.")


async def important_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    rows = list_important_messages(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("Важных сообщений нет. Удивительно здоровая ситуация.")
        return

    lines = []
    for row in rows:
        text = row["source_text"].replace("\n", " ")[:180]
        note = f" - {row['note']}" if row["note"] else ""
        lines.append(f"#{row['id']} / msg {row['message_id']}{note}\n{text}")

    await update.message.reply_text("\n\n".join(lines)[:3500])


async def important_delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /important_delete 3")
        return

    ok = delete_important_message(int(context.args[0]), chat_id=update.effective_chat.id)
    await update.message.reply_text("Удалено." if ok else "Не нашла такое важное сообщение.")


async def important_clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    deleted = clear_important_messages(chat_id=update.effective_chat.id)
    await update.message.reply_text(f"Важные сообщения этого чата очищены: {deleted}.")


async def clear_media_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Пиши так: /clear_media sad\nИли /clear_media_all, если правда хочешь снести весь медиа-склад.")
        return

    category = context.args[0].lower()
    deleted = clear_media(category=category)
    clear_media_seen()
    await update.message.reply_text(f"Медиа категории {category} удалено: {deleted}. История показов медиа сброшена.")


async def clear_media_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    deleted = clear_media()
    clear_media_seen()
    await update.message.reply_text(f"Все медиа удалены: {deleted}. Отдельная кнопка с топором, поздравляю.")


async def clear_media_seen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if context.args and context.args[0].lower() == "all":
        deleted = clear_media_seen()
        await update.message.reply_text(f"История показов медиа очищена везде: {deleted}.")
        return

    deleted = clear_media_seen(chat_id=update.effective_chat.id)
    await update.message.reply_text(f"История показов медиа очищена для этого чата: {deleted}.")


async def set_tts_voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text(
            "Пиши так: /set_tts_voice shimmer\n"
            "Варианты: " + ", ".join(SUPPORTED_TTS_VOICES)
        )
        return

    set_tts_voice(context.args[0])
    await update.message.reply_text(f"Голос установлен: {get_tts_voice()}.")


async def set_tts_model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Пиши так: /set_tts_model tts-1-hd")
        return

    set_tts_model(context.args[0])
    await update.message.reply_text(f"TTS-модель установлена: {get_tts_model()}.")


async def test_voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    voice = context.args[0].lower() if context.args else get_tts_voice()

    if voice not in SUPPORTED_TTS_VOICES:
        await update.message.reply_text(
            "Не знаю такой голос. Варианты:\n" + ", ".join(SUPPORTED_TTS_VOICES)
        )
        return

    text = " ".join(context.args[1:]).strip() if len(context.args) > 1 else TEST_VOICE_TEXT

    await update.message.reply_text(f"Тестирую голос: {voice}.")
    await send_voice_file(update, context, text, voice_override=voice)


async def test_voices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    voices = [arg.lower() for arg in context.args if arg.lower() in SUPPORTED_TTS_VOICES]

    if not voices:
        voices = ["nova", "shimmer", "alloy", "fable", "onyx"]

    voices = voices[:6]

    await update.message.reply_text(
        "Проверяю голоса: " + ", ".join(voices) + ".\n"
        "Это обходит шанс и cooldown, так что не устраивай дегустацию на весь день."
    )

    for voice in voices:
        await update.message.reply_text(f"{voice}:")
        ok = await send_voice_file(update, context, TEST_VOICE_TEXT, voice_override=voice)

        if not ok:
            break

        await asyncio.sleep(0.8)


async def answer_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, save_text: str = None, grouped_messages_count=1):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    touch_chat(user_id, chat_id)

    history = get_history(user_id, chat_id)
    previous_answer = get_last_assistant_answer(user_id, chat_id)

    answer = generate_answer(
        user_id=user_id,
        chat_id=chat_id,
        user_text=user_text,
        history=history,
        previous_answer=previous_answer,
    )
    answer = clean_forbidden_phrases(ensure_visible_punctuation(answer))

    save_message(user_id, chat_id, "user", save_text or user_text)

    if not is_provider_failure_answer(answer):
        save_message(user_id, chat_id, "assistant", answer)

    await maybe_react_to_user_message(update, context, user_text, answer)

    reply_to_message_id = choose_reply_to_message_id(update, grouped_messages_count=grouped_messages_count)
    await send_humanized_reply(
        update,
        context,
        answer,
        user_text=user_text,
        reply_to_message_id=reply_to_message_id,
    )

    if not is_provider_failure_answer(answer):
        await maybe_send_media(update, user_text + "\n" + answer, get_current_mood())


async def process_text_buffer_job(context: ContextTypes.DEFAULT_TYPE):
    key = context.job.data.get("key") if context.job and context.job.data else None
    if not key:
        return

    entry = PENDING_TEXT_BUFFERS.pop(key, None)
    if not entry:
        return

    items = entry.get("items") or []
    if not items:
        return

    update = entry["update"]
    user_text = make_grouped_user_text(items)
    save_text = make_grouped_save_text(items)

    set_setting("last_buffer_messages_count", str(len(items)))
    await answer_user_text(
        update,
        context,
        user_text,
        save_text=save_text,
        grouped_messages_count=len(items),
    )


async def queue_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.job_queue:
        ai_text = build_reply_context_text(update, update.message.text)
        await answer_user_text(update, context, ai_text, save_text=update.message.text)
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    key = f"{chat_id}:{user_id}"
    delay = get_message_buffer_seconds()

    entry = PENDING_TEXT_BUFFERS.get(key)
    if entry and entry.get("job"):
        try:
            entry["job"].schedule_removal()
        except Exception:
            pass

    if not entry:
        entry = {"items": []}

    raw_text = update.message.text
    ai_text = build_reply_context_text(update, raw_text)

    entry["items"].append({"raw_text": raw_text, "ai_text": ai_text})
    entry["update"] = update
    entry["job"] = context.job_queue.run_once(
        process_text_buffer_job,
        when=delay,
        data={"key": key},
        name=f"message_buffer:{key}",
    )

    PENDING_TEXT_BUFFERS[key] = entry


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if get_message_buffer_mode() == "on":
        await queue_text_message(update, context)
        return

    ai_text = build_reply_context_text(update, update.message.text)
    await answer_user_text(update, context, ai_text, save_text=update.message.text)


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.voice:
        return

    if get_voice_input() != "on":
        return

    voice_path = None
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        file = await update.message.voice.get_file()
        temp_dir = Path(tempfile.gettempdir())
        voice_path = temp_dir / f"soiq_in_voice_{update.message.message_id}.ogg"
        await file.download_to_drive(custom_path=str(voice_path))

        transcript = transcribe_audio_file(voice_path)
        if not transcript:
            await update.message.reply_text("Не разобрала голосовое. Технологии опять сделали вид, что они цивилизация.")
            return

        user_text = "[голосовое сообщение]\n" + transcript
        user_text_with_context = build_reply_context_text(update, user_text)
        await answer_user_text(update, context, user_text_with_context, save_text=user_text)

    except Exception as error:
        print("voice input failed:")
        print(error)
        await update.message.reply_text("Голосовое не распозналось. Где-то в платной трубе опять застрял звук.")

    finally:
        try:
            if voice_path:
                Path(voice_path).unlink(missing_ok=True)
        except Exception:
            pass


async def photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return

    if get_image_input() != "on":
        return

    image_path = None
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        photo = update.message.photo[-1]
        file = await photo.get_file()
        temp_dir = Path(tempfile.gettempdir())
        image_path = temp_dir / f"soiq_in_image_{update.message.message_id}.jpg"
        await file.download_to_drive(custom_path=str(image_path))

        caption = update.message.caption or ""
        description = describe_image_file(image_path, caption=caption)
        if not description:
            await update.message.reply_text("Картинку не разобрала. Великолепная эпоха умных машин, да.")
            return

        user_text = "[картинка]\n" + description
        if caption:
            user_text += "\nПодпись пользователя: " + caption

        user_text_with_context = build_reply_context_text(update, user_text)
        await answer_user_text(update, context, user_text_with_context, save_text=user_text)

    except Exception as error:
        print("image input failed:")
        print(error)
        await update.message.reply_text("Картинку не распознала. Провайдер снова лег лицом в серверный пол.")

    finally:
        try:
            if image_path:
                Path(image_path).unlink(missing_ok=True)
        except Exception:
            pass



async def channel_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(channel_status_text())


async def channel_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_channel_enabled(True)
    await update.message.reply_text("Постинг в канал включен. Маленький дневник пустоты получил расписание.")


async def channel_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_channel_enabled(False)
    await update.message.reply_text("Постинг в канал выключен.")


async def set_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Пиши так: /set_channel @channel_username или /set_channel -1001234567890")
        return

    value = context.args[0].strip()
    set_channel_id(value)
    await update.message.reply_text(f"Канал установлен: {value}")


async def set_channel_hours_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_channel_hours 12")
        return

    set_channel_hours(int(context.args[0]))
    await update.message.reply_text(channel_status_text())


async def set_channel_chance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_channel_chance 35")
        return

    set_channel_chance(int(context.args[0]))
    await update.message.reply_text(channel_status_text())


async def set_channel_mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Пиши так: /set_channel_mode static|generated|mixed")
        return

    set_channel_mode(context.args[0])
    await update.message.reply_text(channel_status_text())


async def set_channel_format_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Пиши так: /set_channel_format diary|review|mixed")
        return

    set_channel_format(context.args[0])
    await update.message.reply_text(channel_status_text())


async def channel_post_now_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    try:
        ok, result = await send_channel_post(context.bot, force=True)
    except Exception as error:
        await update.message.reply_text(f"Не смогла отправить в канал: {error}")
        return

    await update.message.reply_text("Отправила в канал." if ok else f"Не отправила: {result}")


async def channel_generate_now_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    try:
        ok, result = await send_channel_post(context.bot, force=True, force_generated=True)
    except Exception as error:
        await update.message.reply_text(f"Не смогла сгенерировать пост в канал: {error}")
        return

    await update.message.reply_text("Сгенерировала и отправила в канал." if ok else f"Не отправила: {result}")


async def clear_channel_recent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin.is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    clear_channel_recent()
    await update.message.reply_text("История повторов канала очищена.")

def register_handlers(app):
    schedule_idle_jobs(app)
    schedule_channel_jobs(app)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", admin.myid))
    app.add_handler(CommandHandler("admin", admin.admin_menu))
    app.add_handler(CommandHandler("admin_help", admin.admin_help))
    app.add_handler(CommandHandler("status", admin.status))
    app.add_handler(CommandHandler("debug", admin.debug_cmd))
    app.add_handler(CommandHandler("mood", admin.mood))
    app.add_handler(CommandHandler("set_mood", admin.set_mood))
    app.add_handler(CommandHandler("auto_mood_on", admin.auto_mood_on))
    app.add_handler(CommandHandler("auto_mood_off", admin.auto_mood_off))
    app.add_handler(CommandHandler("style_mode", admin.style_mode_cmd))
    app.add_handler(CommandHandler("set_style_mode", admin.set_style_mode_cmd))
    app.add_handler(CommandHandler("auto_style_on", admin.auto_style_on_cmd))
    app.add_handler(CommandHandler("auto_style_off", admin.auto_style_off_cmd))
    app.add_handler(CommandHandler("lowercase_on", admin.lowercase_on_cmd))
    app.add_handler(CommandHandler("lowercase_off", admin.lowercase_off_cmd))
    app.add_handler(CommandHandler("lowercase_random", admin.lowercase_random_cmd))
    app.add_handler(CommandHandler("reload_files", admin.reload_files_cmd))
    app.add_handler(CommandHandler("set_media_chance", admin.set_media_chance_cmd))
    app.add_handler(CommandHandler("add_sticker", admin.add_sticker_cmd))
    app.add_handler(CommandHandler("add_photo", admin.add_photo_cmd))
    app.add_handler(CommandHandler("add_animation", admin.add_animation_cmd))
    app.add_handler(CommandHandler("add_link", admin.add_link_cmd))
    app.add_handler(CommandHandler("media", admin.media_cmd))
    app.add_handler(CommandHandler("media_list", admin.media_list_cmd))
    app.add_handler(CommandHandler("send_media", admin.send_media_cmd))
    app.add_handler(CommandHandler("delete_media", admin.delete_media_cmd))
    app.add_handler(CommandHandler("remember_global", admin.remember_global_cmd))
    app.add_handler(CommandHandler("show_global", admin.show_global_cmd))
    app.add_handler(CommandHandler("forget_global", admin.forget_global_cmd))
    app.add_handler(CommandHandler("remember_user", admin.remember_user_cmd))
    app.add_handler(CommandHandler("show_user_memory", admin.show_user_memory_cmd))
    app.add_handler(CommandHandler("forget_user", admin.forget_user_cmd))
    app.add_handler(CommandHandler("show_style", admin.show_style))
    app.add_handler(CommandHandler("reload_style", admin.reload_style))
    app.add_handler(CommandHandler("clear_my_memory", admin.clear_my_memory_cmd))
    app.add_handler(CommandHandler("clear_all_memory", admin.clear_all_memory_cmd))
    app.add_handler(CommandHandler("idle_on", admin.idle_on_cmd))
    app.add_handler(CommandHandler("idle_off", admin.idle_off_cmd))
    app.add_handler(CommandHandler("set_idle_hours", admin.set_idle_hours_cmd))
    app.add_handler(CommandHandler("set_idle_chance", admin.set_idle_chance_cmd))
    app.add_handler(CommandHandler("idle_now", idle_now_cmd))
    app.add_handler(CommandHandler("voice_off", admin.voice_off_cmd))
    app.add_handler(CommandHandler("voice_on", admin.voice_on_cmd))
    app.add_handler(CommandHandler("voice_random", admin.voice_random_cmd))
    app.add_handler(CommandHandler("set_voice_chance", admin.set_voice_chance_cmd))
    app.add_handler(CommandHandler("set_tts_voice", set_tts_voice_cmd))
    app.add_handler(CommandHandler("set_tts_model", set_tts_model_cmd))
    app.add_handler(CommandHandler("test_voice", test_voice_cmd))
    app.add_handler(CommandHandler("test_voices", test_voices_cmd))
    app.add_handler(CommandHandler("reactions", reactions_cmd))
    app.add_handler(CommandHandler("reactions_on", reactions_on_cmd))
    app.add_handler(CommandHandler("reactions_off", reactions_off_cmd))
    app.add_handler(CommandHandler("set_reaction_chance", set_reaction_chance_cmd))
    app.add_handler(CommandHandler("quotes", quotes_cmd))
    app.add_handler(CommandHandler("reload_quotes", reload_quotes_cmd))
    app.add_handler(CommandHandler("set_quote_chance", set_quote_chance_cmd))
    app.add_handler(CommandHandler("set_quote_match", set_quote_match_cmd))
    app.add_handler(CommandHandler("paid_fallback_on", paid_fallback_on_cmd))
    app.add_handler(CommandHandler("paid_fallback_off", paid_fallback_off_cmd))
    app.add_handler(CommandHandler("paid_complex_on", paid_complex_on_cmd))
    app.add_handler(CommandHandler("paid_complex_off", paid_complex_off_cmd))
    app.add_handler(CommandHandler("paid_status", paid_status_cmd))
    app.add_handler(CommandHandler("groq_on", groq_on_cmd))
    app.add_handler(CommandHandler("groq_off", groq_off_cmd))
    app.add_handler(CommandHandler("groq_status", groq_status_cmd))
    app.add_handler(CommandHandler("voice_input_on", voice_input_on_cmd))
    app.add_handler(CommandHandler("voice_input_off", voice_input_off_cmd))
    app.add_handler(CommandHandler("vision_on", vision_on_cmd))
    app.add_handler(CommandHandler("vision_off", vision_off_cmd))
    app.add_handler(CommandHandler("multimodal_status", multimodal_status_cmd))
    app.add_handler(CommandHandler("clear_media", clear_media_cmd))
    app.add_handler(CommandHandler("clear_media_all", clear_media_all_cmd))
    app.add_handler(CommandHandler("clear_media_seen", clear_media_seen_cmd))
    app.add_handler(CommandHandler("buffer_on", message_buffer_on_cmd))
    app.add_handler(CommandHandler("buffer_off", message_buffer_off_cmd))
    app.add_handler(CommandHandler("set_buffer_seconds", set_message_buffer_seconds_cmd))
    app.add_handler(CommandHandler("buffer_status", message_buffer_status_cmd))
    app.add_handler(CommandHandler("reply_on", reply_on_cmd))
    app.add_handler(CommandHandler("reply_random", reply_random_cmd))
    app.add_handler(CommandHandler("reply_off", reply_off_cmd))
    app.add_handler(CommandHandler("set_reply_chance", set_reply_chance_cmd))
    app.add_handler(CommandHandler("reply_status", reply_status_cmd))
    app.add_handler(CommandHandler("pin", pin_cmd))
    app.add_handler(CommandHandler("pin_last", pin_last_cmd))
    app.add_handler(CommandHandler("unpin", unpin_cmd))
    app.add_handler(CommandHandler("important", important_cmd))
    app.add_handler(CommandHandler("important_list", important_list_cmd))
    app.add_handler(CommandHandler("important_delete", important_delete_cmd))
    app.add_handler(CommandHandler("important_clear", important_clear_cmd))
    app.add_handler(CommandHandler("channel_status", channel_status_cmd))
    app.add_handler(CommandHandler("channel_on", channel_on_cmd))
    app.add_handler(CommandHandler("channel_off", channel_off_cmd))
    app.add_handler(CommandHandler("set_channel", set_channel_cmd))
    app.add_handler(CommandHandler("set_channel_hours", set_channel_hours_cmd))
    app.add_handler(CommandHandler("set_channel_chance", set_channel_chance_cmd))
    app.add_handler(CommandHandler("set_channel_mode", set_channel_mode_cmd))
    app.add_handler(CommandHandler("set_channel_format", set_channel_format_cmd))
    app.add_handler(CommandHandler("channel_post_now", channel_post_now_cmd))
    app.add_handler(CommandHandler("channel_generate_now", channel_generate_now_cmd))
    app.add_handler(CommandHandler("clear_channel_recent", clear_channel_recent_cmd))
    app.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.VOICE, voice_message))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
