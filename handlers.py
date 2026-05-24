import random
import re
import asyncio

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

import admin
from ai import generate_answer
from memory import save_message, get_history, get_last_assistant_answer
from moods import get_current_mood
from media import maybe_send_media


def split_sentences_safely(text):
    # Не режем после 1. 2. 3., чтобы не получалось "2." отдельно от текста пункта.
    parts = re.split(r"(?<!\b\d)(?<=[.!?])\s+(?=[А-ЯA-Zа-яa-z])", text.strip())
    return [part.strip() for part in parts if part.strip()]


def split_answer_randomly(text):
    if not text:
        return []

    text = text.strip()

    # Часто оставляем одним сообщением.
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


async def send_humanized_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str):
    parts = split_answer_randomly(answer)

    for index, part in enumerate(parts):
        # Чем длиннее кусок, тем дольше "печатает".
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
    await update.message.reply_text(
        "Qq.\nПозвони, как напишешь.\nВпрочем, интереса отвечать тебе все еще нет.\n:)",
        parse_mode=None,
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_text = update.message.text

    history = get_history(user_id, chat_id)
    previous_answer = get_last_assistant_answer(user_id, chat_id)

    answer = generate_answer(
        user_id=user_id,
        chat_id=chat_id,
        user_text=user_text,
        history=history,
        previous_answer=previous_answer,
    )

    save_message(user_id, chat_id, "user", user_text)
    save_message(user_id, chat_id, "assistant", answer)

    await send_humanized_reply(update, context, answer)

    await maybe_send_media(update, user_text + "\n" + answer, get_current_mood())


def register_handlers(app):
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
    app.add_handler(CallbackQueryHandler(admin.admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
