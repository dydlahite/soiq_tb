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
from forbidden import clean_forbidden_phrases
from memory import save_message, get_history, get_last_assistant_answer
from moods import get_current_mood
from media import maybe_send_media, clear_media, clear_media_seen, get_random_media, send_media_item
from idle import touch_chat, schedule_idle_jobs, send_idle_now
from multimodal import (
    transcribe_audio_file,
    describe_image_file,
    set_voice_input,
    set_image_input,
    get_voice_input,
    get_image_input,
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
REACTION_RULES_PATH = "reaction_rules.txt"



def is_provider_failure_answer(answer):
    return bool(answer and answer.strip().startswith(PROVIDER_FAILURE_PREFIX))


def split_sentences_safely(text):
    parts = re.split(r"(?<!\b\d)(?<=[.!?])\s+(?=[А-ЯA-Zа-яa-z])", text.strip())
    return [part.strip() for part in parts if part.strip()]


def ensure_visible_punctuation(text):
    if not text:
        return text

    text = text.replace("* .. :) *", ".. :)")
    lines = text.splitlines()
    fixed = []

    for line in lines:
        stripped = line.rstrip()

        if not stripped:
            fixed.append(stripped)
            continue

        if stripped.endswith(".. :)"):
            fixed.append(stripped)
            continue

        if stripped[-1] not in ".!?":
            stripped += "."

        fixed.append(stripped)

    return "\n".join(fixed).strip()


def add_human_line_breaks(text):
    if not text or "\n" in text:
        return text

    if len(text) < 75 or len(text) > 520:
        return text

    if random.randint(1, 100) > 46:
        return text

    sentences = split_sentences_safely(text)

    if len(sentences) < 2 or len(sentences) > 5:
        return text

    lines = []

    for sentence in sentences:
        if lines and len(lines[-1]) + len(sentence) < 62 and random.randint(1, 100) <= 30:
            lines[-1] += " " + sentence
        else:
            lines.append(sentence)

    if len(lines) < 2:
        return text

    return "\n".join(lines)


def split_answer_randomly(text):
    if not text:
        return []

    text = text.strip()

    if len(text) < 180 or random.randint(1, 100) <= 45:
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

    target_len = random.randint(180, 360)
    chunks = []
    current = ""

    for unit in units:
        if not current:
            current = unit
            continue

        if len(current) + len(unit) + 1 <= target_len or len(chunks) >= 9:
            current += " " + unit
        else:
            chunks.append(current.strip())
            current = unit

    if current:
        chunks.append(current.strip())

    while len(chunks) > 10:
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


async def send_voice_file(update: Update, text: str, voice_override=None, model_override=None):
    voice_path = None

    try:
        voice_path, is_voice = make_tts_file(
            text,
            voice_override=voice_override,
            model_override=model_override,
        )

        with open(voice_path, "rb") as file:
            if is_voice:
                await update.message.reply_voice(voice=file)
            else:
                await update.message.reply_audio(audio=file)

        return True

    except Exception as error:
        print("TTS failed:")
        print(error)
        await update.message.reply_text(f"Голос {voice_override or get_tts_voice()} не вышел. Провайдер снова устроил цирк в серверной.")
        return False

    finally:
        cleanup_voice_file(voice_path)


async def send_voice_reply(update: Update, answer: str):
    ok = await send_voice_file(update, answer)

    if ok:
        record_voice_sent()

    return ok


async def send_humanized_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str, user_text: str = ""):
    answer = ensure_visible_punctuation(answer)

    if should_send_voice(answer, user_text=user_text, mood=get_current_mood()):
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.RECORD_VOICE,
        )

        if await send_voice_reply(update, answer):
            return

    parts = split_answer_randomly(answer)

    for index, part in enumerate(parts):
        part = ensure_visible_punctuation(add_human_line_breaks(part))

        delay = len(part) / random.uniform(45, 75)
        delay += random.uniform(0.3, 1.0)

        if index == 0:
            delay = min(delay, 5.5)
        else:
            delay = min(delay, 7.0)

        delay = max(0.6, delay)

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )

        await asyncio.sleep(delay)
        await update.message.reply_text(part, parse_mode=None)


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
    await send_voice_file(update, text, voice_override=voice)


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
        ok = await send_voice_file(update, TEST_VOICE_TEXT, voice_override=voice)

        if not ok:
            break

        await asyncio.sleep(0.8)


async def answer_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, save_text: str = None):
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
    await send_humanized_reply(update, context, answer, user_text=user_text)

    if not is_provider_failure_answer(answer):
        await maybe_send_media(update, user_text + "\n" + answer, get_current_mood())


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    await answer_user_text(update, context, update.message.text)


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
        await answer_user_text(update, context, user_text, save_text=user_text)

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

        await answer_user_text(update, context, user_text, save_text=user_text)

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


def register_handlers(app):
    schedule_idle_jobs(app)

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
    app.add_handler(CommandHandler("paid_fallback_on", paid_fallback_on_cmd))
    app.add_handler(CommandHandler("paid_fallback_off", paid_fallback_off_cmd))
    app.add_handler(CommandHandler("paid_complex_on", paid_complex_on_cmd))
    app.add_handler(CommandHandler("paid_complex_off", paid_complex_off_cmd))
    app.add_handler(CommandHandler("paid_status", paid_status_cmd))
    app.add_handler(CommandHandler("voice_input_on", voice_input_on_cmd))
    app.add_handler(CommandHandler("voice_input_off", voice_input_off_cmd))
    app.add_handler(CommandHandler("vision_on", vision_on_cmd))
    app.add_handler(CommandHandler("vision_off", vision_off_cmd))
    app.add_handler(CommandHandler("multimodal_status", multimodal_status_cmd))
    app.add_handler(CommandHandler("clear_media", clear_media_cmd))
    app.add_handler(CommandHandler("clear_media_all", clear_media_all_cmd))
    app.add_handler(CommandHandler("clear_media_seen", clear_media_seen_cmd))
    app.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.VOICE, voice_message))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
