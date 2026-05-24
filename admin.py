from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database import cursor, get_setting
from memory import clear_all_memory, clear_user_memory, count_messages, remember, forget, list_memories
from moods import MOODS, get_current_mood, set_mood_value, enable_auto_mood, disable_auto_mood
from media import add_media, list_media_categories, list_media_items, delete_media, set_media_chance, get_media_chance, get_random_media
from personality import load_personality, ensure_personality_file


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Статус", callback_data="admin_status"), InlineKeyboardButton("Настроение", callback_data="admin_mood")],
        [InlineKeyboardButton("Автонастроение ON", callback_data="admin_auto_on"), InlineKeyboardButton("Автонастроение OFF", callback_data="admin_auto_off")],
        [InlineKeyboardButton("Медиа", callback_data="admin_media"), InlineKeyboardButton("Память", callback_data="admin_memory")],
    ])


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой Telegram ID: {update.effective_user.id}")


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа. Какая дерзкая попытка.")
        return
    await update.message.reply_text("Админка. Почти цивилизация.", reply_markup=admin_keyboard())


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text(
        "/myid\n/admin\n/status\n/mood\n/set_mood tired\n/set_mood tired 6\n"
        "/auto_mood_on\n/auto_mood_off\n/set_media_chance 15\n"
        "/add_sticker funny — ответом на стикер\n/add_photo sad — ответом на фото\n"
        "/add_animation funny — ответом на gif\n/add_link music https://... название\n"
        "/media\n/media_list\n/send_media funny\n/delete_media 3\n"
        "/remember_global ключ значение\n/show_global\n/forget_global ключ\n"
        "/remember_user ключ значение\n/show_user_memory\n/forget_user ключ\n"
        "/show_style\n/reload_style\n/clear_my_memory\n/clear_all_memory"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    cursor.execute("SELECT COUNT(*) AS count FROM media")
    media_count = cursor.fetchone()["count"]
    await update.message.reply_text(
        f"Бот работает.\nНастроение: {get_current_mood()}\nАвтонастроение: {get_setting('auto_mood', 'off')}\n"
        f"Сообщений в истории: {count_messages()}\nМедиа: {media_count}\nШанс медиа: {get_media_chance()}%"
    )


async def mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текущее настроение: {get_current_mood()}")


async def set_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args:
        await update.message.reply_text("Пиши так: /set_mood tired\nДоступные: " + ", ".join(MOODS.keys()))
        return
    new_mood = context.args[0].lower()
    if new_mood not in MOODS:
        await update.message.reply_text("Нет такого настроения. Доступные:\n" + ", ".join(MOODS.keys()))
        return
    hours = int(context.args[1]) if len(context.args) >= 2 and context.args[1].isdigit() else None
    set_mood_value(new_mood, hours=hours)
    await update.message.reply_text(f"Настроение установлено: {new_mood}" + (f" на {hours} ч." if hours else ""))


async def auto_mood_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    enable_auto_mood()
    await update.message.reply_text("Автонастроение включено.")


async def auto_mood_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    disable_auto_mood()
    await update.message.reply_text("Автонастроение выключено.")


async def set_media_chance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_media_chance 15")
        return
    set_media_chance(int(context.args[0]))
    await update.message.reply_text(f"Шанс медиа: {get_media_chance()}%")


async def add_sticker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args:
        await update.message.reply_text("Пиши ответом на стикер: /add_sticker funny")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
        await update.message.reply_text("Нужно ответить этой командой на стикер.")
        return
    add_media("sticker", context.args[0].lower(), file_id=update.message.reply_to_message.sticker.file_id)
    await update.message.reply_text("Стикер сохранен.")


async def add_photo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args:
        await update.message.reply_text("Пиши ответом на фото: /add_photo sad")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Нужно ответить этой командой на фото.")
        return
    add_media("photo", context.args[0].lower(), file_id=update.message.reply_to_message.photo[-1].file_id)
    await update.message.reply_text("Фото сохранено.")


async def add_animation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args:
        await update.message.reply_text("Пиши ответом на gif: /add_animation funny")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.animation:
        await update.message.reply_text("Нужно ответить этой командой на gif.")
        return
    add_media("animation", context.args[0].lower(), file_id=update.message.reply_to_message.animation.file_id)
    await update.message.reply_text("GIF сохранена.")


async def add_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Пиши так: /add_link music https://... название")
        return
    category = context.args[0].lower()
    url = context.args[1]
    title = " ".join(context.args[2:]) if len(context.args) > 2 else None
    add_media("link", category, url=url, title=title)
    await update.message.reply_text("Ссылка сохранена.")


async def media_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    rows = list_media_categories()
    if not rows:
        await update.message.reply_text("Медиа нет.")
        return
    await update.message.reply_text("\n".join([f"{r['category']} / {r['media_type']}: {r['count']}" for r in rows]))


async def media_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    rows = list_media_items()
    if not rows:
        await update.message.reply_text("Медиа нет.")
        return
    await update.message.reply_text("\n".join([f"{r['id']}. {r['media_type']} / {r['category']} {r['title'] or r['url'] or ''}" for r in rows])[:3500])


async def send_media_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    item = get_random_media(context.args[0].lower() if context.args else None)
    if not item:
        await update.message.reply_text("Ничего не найдено.")
        return
    if item["media_type"] == "sticker":
        await update.message.reply_sticker(item["file_id"])
    elif item["media_type"] == "photo":
        await update.message.reply_photo(item["file_id"])
    elif item["media_type"] == "animation":
        await update.message.reply_animation(item["file_id"])
    elif item["media_type"] == "link":
        await update.message.reply_text(f"{item['title'] or 'Ссылка'}\n{item['url']}")


async def delete_media_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /delete_media 3")
        return
    await update.message.reply_text("Удалено." if delete_media(int(context.args[0])) else "Не нашла такое медиа.")


async def remember_global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Пиши так: /remember_global ключ значение")
        return
    remember("global", context.args[0], " ".join(context.args[1:]))
    await update.message.reply_text("Запомнила глобально.")


async def show_global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    rows = list_memories("global")
    await update.message.reply_text("\n".join([f"{k}: {v}" for k, v in rows])[:3500] or "Глобальная память пуста.")


async def forget_global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args:
        await update.message.reply_text("Пиши так: /forget_global ключ")
        return
    forget("global", context.args[0])
    await update.message.reply_text("Удалено.")


async def remember_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Пиши так: /remember_user ключ значение")
        return
    remember("user", context.args[0], " ".join(context.args[1:]), update.effective_user.id, update.effective_chat.id)
    await update.message.reply_text("Запомнила.")


async def show_user_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = list_memories("user", update.effective_user.id, update.effective_chat.id)
    await update.message.reply_text("\n".join([f"{k}: {v}" for k, v in rows])[:3500] or "Память об этом чате пуста.")


async def forget_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пиши так: /forget_user ключ")
        return
    forget("user", context.args[0], update.effective_user.id, update.effective_chat.id)
    await update.message.reply_text("Удалено.")


async def show_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text(load_personality()[:3500])


async def reload_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    ensure_personality_file()
    await update.message.reply_text("personality.txt на месте.")


async def clear_my_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_user_memory(update.effective_user.id, update.effective_chat.id)
    await update.message.reply_text("Твоя история очищена.")


async def clear_all_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    clear_all_memory()
    await update.message.reply_text("Вся история очищена.")


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        await query.edit_message_text("Нет доступа.")
        return
    data = query.data
    if data == "admin_auto_on":
        enable_auto_mood()
        await query.edit_message_text("Автонастроение включено.", reply_markup=admin_keyboard())
    elif data == "admin_auto_off":
        disable_auto_mood()
        await query.edit_message_text("Автонастроение выключено.", reply_markup=admin_keyboard())
    elif data == "admin_status":
        await query.edit_message_text(f"Бот работает.\nНастроение: {get_current_mood()}\nСообщений: {count_messages()}\nШанс медиа: {get_media_chance()}%", reply_markup=admin_keyboard())
    elif data == "admin_mood":
        await query.edit_message_text("Настроения:\n" + ", ".join(MOODS.keys()), reply_markup=admin_keyboard())
    elif data == "admin_media":
        rows = list_media_categories()
        text = "Медиа нет." if not rows else "\n".join([f"{r['category']} / {r['media_type']}: {r['count']}" for r in rows])
        await query.edit_message_text(text, reply_markup=admin_keyboard())
    elif data == "admin_memory":
        await query.edit_message_text(f"Сообщений в истории: {count_messages()}", reply_markup=admin_keyboard())
