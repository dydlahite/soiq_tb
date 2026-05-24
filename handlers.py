import random
import re
import asyncio

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

import admin
from ai import generate_answer
from memory import save_message, get_history, get_last_assistant_answer
from moods import get_current_mood
from media import maybe_send_media

def split_answer_randomly(text):
    if not text:
        return []

    # Часто оставляем одним сообщением, чтобы бот не строчил как нервный человек в 3 ночи.
    if len(text) < 140 or random.randint(1, 100) <= 55:
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 2:
        return [text]

    parts_count = random.randint(2, min(5, len(sentences)))
    chunks = [[] for _ in range(parts_count)]

    for index, sentence in enumerate(sentences):
        chunk_index = min(index * parts_count // len(sentences), parts_count - 1)
        chunks[chunk_index].append(sentence)

    result = [" ".join(chunk).strip() for chunk in chunks if chunk]

    return result[:10]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Qq.\nПозвони, как напишешь.\nВпрочем, интереса отвечать тебе все еще нет.\n:)")


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

    for part in split_answer_randomly(answer):
    await update.message.reply_text(part)
    await asyncio.sleep(random.uniform(0.4, 1.3))

    await maybe_send_media(update, user_text + "\n" + answer, get_current_mood())


def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", admin.myid))
    app.add_handler(CommandHandler("admin", admin.admin_menu))
    app.add_handler(CommandHandler("admin_help", admin.admin_help))
    app.add_handler(CommandHandler("status", admin.status))
    app.add_handler(CommandHandler("mood", admin.mood))
    app.add_handler(CommandHandler("set_mood", admin.set_mood))
    app.add_handler(CommandHandler("auto_mood_on", admin.auto_mood_on))
    app.add_handler(CommandHandler("auto_mood_off", admin.auto_mood_off))
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
