from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

import admin
from ai import generate_answer
from memory import save_message, get_history, get_last_assistant_answer
from moods import get_current_mood
from media import maybe_send_media


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

    await update.message.reply_text(answer)

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
