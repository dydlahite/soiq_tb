from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database import cursor, get_setting, set_setting
from memory import clear_all_memory, clear_user_memory, count_messages, remember, forget, list_memories
from moods import MOODS, get_current_mood, set_mood_value, enable_auto_mood, disable_auto_mood
from media import add_media, list_media_categories, list_media_items, delete_media, set_media_chance, get_media_chance, get_random_media
from personality import load_personality, ensure_personality_file


STYLE_MODES = ["normal", "ornate", "messy", "dry", "angry", "soft"]


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


def keyboard(rows):
    return InlineKeyboardMarkup(rows)


def back_button():
    return [InlineKeyboardButton("Назад", callback_data="admin_main")]


def admin_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("Статус", callback_data="admin_status"),
            InlineKeyboardButton("Debug", callback_data="admin_debug"),
        ],
        [
            InlineKeyboardButton("Настроение", callback_data="admin_mood_page"),
            InlineKeyboardButton("Режим речи", callback_data="admin_style_page"),
        ],
        [
            InlineKeyboardButton("Автонастроение", callback_data="admin_auto_mood_page"),
            InlineKeyboardButton("Автостиль", callback_data="admin_auto_style_page"),
        ],
        [
            InlineKeyboardButton("lowercase", callback_data="admin_lowercase_page"),
            InlineKeyboardButton("Медиа", callback_data="admin_media_page"),
        ],
        [
            InlineKeyboardButton("Память", callback_data="admin_memory_page"),
            InlineKeyboardButton("Помощь", callback_data="admin_help_page"),
        ],
    ])


def mood_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("neutral", callback_data="admin_set_mood:neutral"),
            InlineKeyboardButton("tired", callback_data="admin_set_mood:tired"),
        ],
        [
            InlineKeyboardButton("cold", callback_data="admin_set_mood:cold"),
            InlineKeyboardButton("angry", callback_data="admin_set_mood:angry"),
        ],
        [
            InlineKeyboardButton("soft", callback_data="admin_set_mood:soft"),
            InlineKeyboardButton("playful", callback_data="admin_set_mood:playful"),
        ],
        [
            InlineKeyboardButton("melancholic", callback_data="admin_set_mood:melancholic"),
            InlineKeyboardButton("sarcastic", callback_data="admin_set_mood:sarcastic"),
        ],
        [
            InlineKeyboardButton("Авто ON", callback_data="admin_auto_mood:on"),
            InlineKeyboardButton("Авто OFF", callback_data="admin_auto_mood:off"),
        ],
        back_button(),
    ])


def style_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("normal", callback_data="admin_set_style:normal"),
            InlineKeyboardButton("ornate", callback_data="admin_set_style:ornate"),
        ],
        [
            InlineKeyboardButton("messy", callback_data="admin_set_style:messy"),
            InlineKeyboardButton("dry", callback_data="admin_set_style:dry"),
        ],
        [
            InlineKeyboardButton("angry", callback_data="admin_set_style:angry"),
            InlineKeyboardButton("soft", callback_data="admin_set_style:soft"),
        ],
        [
            InlineKeyboardButton("Автостиль ON", callback_data="admin_auto_style:on"),
            InlineKeyboardButton("Автостиль OFF", callback_data="admin_auto_style:off"),
        ],
        back_button(),
    ])


def lowercase_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("off", callback_data="admin_lowercase:off"),
            InlineKeyboardButton("on", callback_data="admin_lowercase:on"),
            InlineKeyboardButton("random", callback_data="admin_lowercase:random"),
        ],
        back_button(),
    ])


def media_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("0%", callback_data="admin_media_chance:0"),
            InlineKeyboardButton("10%", callback_data="admin_media_chance:10"),
            InlineKeyboardButton("20%", callback_data="admin_media_chance:20"),
            InlineKeyboardButton("35%", callback_data="admin_media_chance:35"),
        ],
        [
            InlineKeyboardButton("Список категорий", callback_data="admin_media_categories"),
            InlineKeyboardButton("Случайное медиа", callback_data="admin_send_random_media"),
        ],
        back_button(),
    ])


def memory_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("Очистить мой чат", callback_data="admin_clear_my_memory_confirm"),
        ],
        [
            InlineKeyboardButton("Очистить ВСЮ историю", callback_data="admin_clear_all_memory_confirm"),
        ],
        [
            InlineKeyboardButton("Глобальная память", callback_data="admin_show_global_memory"),
            InlineKeyboardButton("Память чата", callback_data="admin_show_user_memory"),
        ],
        back_button(),
    ])


def confirm_clear_my_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("Да, очистить мой чат", callback_data="admin_clear_my_memory_do"),
        ],
        back_button(),
    ])


def confirm_clear_all_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("Да, стереть ВСЮ историю", callback_data="admin_clear_all_memory_do"),
        ],
        back_button(),
    ])


def auto_mood_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("Автонастроение ON", callback_data="admin_auto_mood:on"),
            InlineKeyboardButton("Автонастроение OFF", callback_data="admin_auto_mood:off"),
        ],
        back_button(),
    ])


def auto_style_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("Автостиль ON", callback_data="admin_auto_style:on"),
            InlineKeyboardButton("Автостиль OFF", callback_data="admin_auto_style:off"),
        ],
        back_button(),
    ])


def status_text():
    cursor.execute("SELECT COUNT(*) AS count FROM media")
    media_count = cursor.fetchone()["count"]

    return (
        f"Бот работает.\n"
        f"Настроение: {get_current_mood()}\n"
        f"Автонастроение: {get_setting('auto_mood', 'off')}\n"
        f"Режим речи: {get_setting('style_mode', 'normal')}\n"
        f"Последний режим: {get_setting('last_style_mode', 'normal')}\n"
        f"Авторежим речи: {get_setting('auto_style', 'off')}\n"
        f"Провайдер: {get_setting('last_provider', 'нет')}\n"
        f"lowercase: {get_setting('lowercase_mode', 'off')}\n"
        f"Сообщений в истории: {count_messages()}\n"
        f"Медиа: {media_count}\n"
        f"Шанс медиа: {get_media_chance()}%"
    )


def debug_text():
    return (
        f"Провайдер последнего ответа: {get_setting('last_provider', 'нет')}\n"
        f"Последняя попытка провайдера: {get_setting('last_provider_try', 'нет')}\n"
        f"Настроение: {get_current_mood()}\n"
        f"Автонастроение: {get_setting('auto_mood', 'off')}\n"
        f"Режим речи: {get_setting('style_mode', 'normal')}\n"
        f"Последний режим речи: {get_setting('last_style_mode', 'normal')}\n"
        f"Авторежим речи: {get_setting('auto_style', 'off')}\n"
        f"lowercase: {get_setting('lowercase_mode', 'off')}\n"
        f"Шанс медиа: {get_media_chance()}%\n"
        f"Сообщений в истории: {count_messages()}"
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой Telegram ID: {update.effective_user.id}")


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа. Какая дерзкая попытка.")
        return

    await update.message.reply_text(
        "Админка. Теперь с кнопками, чтобы не держать в голове этот словарь заклинаний.",
        reply_markup=admin_keyboard(),
    )


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(
        "/admin — кнопочная панель\n"
        "/debug — что сейчас отвечает и в каком режиме\n"
        "/status — статус\n"
        "/mood — настроение\n"
        "/style_mode — режим речи\n"
        "/clear_my_memory — очистить историю этого чата\n"
        "/clear_all_memory — очистить всю историю\n\n"
        "Остальные команды есть в старом виде, но теперь основное можно тыкать кнопками. Наконец-то прогресс, почти без унижения."
    )


async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(debug_text())


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text(status_text(), reply_markup=admin_keyboard())


async def mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Текущее настроение: {get_current_mood()}", reply_markup=mood_keyboard())


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


async def style_mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Режим речи: {get_setting('style_mode', 'normal')}\n"
        f"Последний режим: {get_setting('last_style_mode', 'normal')}\n"
        f"Авторежим: {get_setting('auto_style', 'off')}\n"
        f"Доступные: {', '.join(STYLE_MODES)}",
        reply_markup=style_keyboard(),
    )


async def set_style_mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    if not context.args:
        await update.message.reply_text("Пиши так: /set_style_mode ornate\nДоступные: " + ", ".join(STYLE_MODES))
        return

    mode = context.args[0].lower()

    if mode not in STYLE_MODES:
        await update.message.reply_text("Нет такого режима. Доступные: " + ", ".join(STYLE_MODES))
        return

    set_setting("style_mode", mode)
    set_setting("auto_style", "off")
    await update.message.reply_text(f"Режим речи установлен: {mode}")


async def auto_style_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("auto_style", "on")
    await update.message.reply_text("Авторежим речи включен.")


async def auto_style_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("auto_style", "off")
    await update.message.reply_text("Авторежим речи выключен.")


async def lowercase_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("lowercase_mode", "on")
    await update.message.reply_text("lowercase включен.")


async def lowercase_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("lowercase_mode", "off")
    await update.message.reply_text("lowercase выключен.")


async def lowercase_random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    set_setting("lowercase_mode", "random")
    await update.message.reply_text("lowercase random включен. Иногда будет писать с маленькой.")


async def reload_files_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return

    await update.message.reply_text("Файлы стиля будут перечитаны при следующем ответе.")


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

    if data == "admin_main":
        await query.edit_message_text(
            "Админка. Тыкательный центр управления маленькой катастрофой.",
            reply_markup=admin_keyboard(),
        )
        return

    if data == "admin_help_page":
        await query.edit_message_text(
            "Основное теперь выбирается кнопками.\n\n"
            "Команды оставлены для ручного режима:\n"
            "/debug, /status, /mood, /style_mode, /clear_my_memory, /clear_all_memory.\n\n"
            "Медиа добавляются командами ответом на файл: /add_sticker funny, /add_photo sad, /add_animation funny.",
            reply_markup=admin_keyboard(),
        )
        return

    if data == "admin_status":
        await query.edit_message_text(status_text(), reply_markup=admin_keyboard())
        return

    if data == "admin_debug":
        await query.edit_message_text(debug_text(), reply_markup=admin_keyboard())
        return

    if data == "admin_mood_page":
        await query.edit_message_text(
            f"Настроение сейчас: {get_current_mood()}\n"
            f"Автонастроение: {get_setting('auto_mood', 'off')}",
            reply_markup=mood_keyboard(),
        )
        return

    if data == "admin_style_page":
        await query.edit_message_text(
            f"Режим речи: {get_setting('style_mode', 'normal')}\n"
            f"Последний режим: {get_setting('last_style_mode', 'normal')}\n"
            f"Авторежим: {get_setting('auto_style', 'off')}",
            reply_markup=style_keyboard(),
        )
        return

    if data == "admin_auto_mood_page":
        await query.edit_message_text(
            f"Автонастроение: {get_setting('auto_mood', 'off')}",
            reply_markup=auto_mood_keyboard(),
        )
        return

    if data == "admin_auto_style_page":
        await query.edit_message_text(
            f"Авторежим речи: {get_setting('auto_style', 'off')}",
            reply_markup=auto_style_keyboard(),
        )
        return

    if data == "admin_lowercase_page":
        await query.edit_message_text(
            f"lowercase: {get_setting('lowercase_mode', 'off')}",
            reply_markup=lowercase_keyboard(),
        )
        return

    if data == "admin_media_page":
        await query.edit_message_text(
            f"Шанс медиа: {get_media_chance()}%\n"
            "Выбери шанс случайной отправки медиа.",
            reply_markup=media_keyboard(),
        )
        return

    if data == "admin_memory_page":
        await query.edit_message_text(
            f"Сообщений в истории: {count_messages()}",
            reply_markup=memory_keyboard(),
        )
        return

    if data.startswith("admin_set_mood:"):
        mood = data.split(":", 1)[1]

        if mood in MOODS:
            set_mood_value(mood)
            await query.edit_message_text(
                f"Настроение установлено: {mood}",
                reply_markup=mood_keyboard(),
            )
        else:
            await query.edit_message_text("Нет такого настроения.", reply_markup=mood_keyboard())
        return

    if data.startswith("admin_auto_mood:"):
        value = data.split(":", 1)[1]

        if value == "on":
            enable_auto_mood()
            text = "Автонастроение включено."
        else:
            disable_auto_mood()
            text = "Автонастроение выключено."

        await query.edit_message_text(text, reply_markup=mood_keyboard())
        return

    if data.startswith("admin_set_style:"):
        mode = data.split(":", 1)[1]

        if mode in STYLE_MODES:
            set_setting("style_mode", mode)
            set_setting("auto_style", "off")
            await query.edit_message_text(
                f"Режим речи установлен: {mode}",
                reply_markup=style_keyboard(),
            )
        else:
            await query.edit_message_text("Нет такого режима.", reply_markup=style_keyboard())
        return

    if data.startswith("admin_auto_style:"):
        value = data.split(":", 1)[1]

        if value == "on":
            set_setting("auto_style", "on")
            text = "Авторежим речи включен."
        else:
            set_setting("auto_style", "off")
            text = "Авторежим речи выключен."

        await query.edit_message_text(text, reply_markup=style_keyboard())
        return

    if data.startswith("admin_lowercase:"):
        value = data.split(":", 1)[1]

        if value not in ["on", "off", "random"]:
            value = "off"

        set_setting("lowercase_mode", value)

        await query.edit_message_text(
            f"lowercase установлен: {value}",
            reply_markup=lowercase_keyboard(),
        )
        return

    if data.startswith("admin_media_chance:"):
        value = data.split(":", 1)[1]

        if value.isdigit():
            set_media_chance(int(value))

        await query.edit_message_text(
            f"Шанс медиа: {get_media_chance()}%",
            reply_markup=media_keyboard(),
        )
        return

    if data == "admin_media_categories":
        rows = list_media_categories()

        if not rows:
            text = "Медиа нет."
        else:
            text = "\n".join([f"{r['category']} / {r['media_type']}: {r['count']}" for r in rows])

        await query.edit_message_text(text[:3500], reply_markup=media_keyboard())
        return

    if data == "admin_send_random_media":
        item = get_random_media()

        if not item:
            await query.edit_message_text("Медиа нет.", reply_markup=media_keyboard())
            return

        await query.edit_message_text("Отправляю случайное медиа.", reply_markup=media_keyboard())

        if item["media_type"] == "sticker":
            await query.message.reply_sticker(item["file_id"])
        elif item["media_type"] == "photo":
            await query.message.reply_photo(item["file_id"])
        elif item["media_type"] == "animation":
            await query.message.reply_animation(item["file_id"])
        elif item["media_type"] == "link":
            await query.message.reply_text(f"{item['title'] or 'Ссылка'}\n{item['url']}")
        return

    if data == "admin_clear_my_memory_confirm":
        await query.edit_message_text(
            "Точно очистить историю этого чата?",
            reply_markup=confirm_clear_my_keyboard(),
        )
        return

    if data == "admin_clear_all_memory_confirm":
        await query.edit_message_text(
            "Точно стереть ВСЮ историю сообщений? Это не красивый жест, это кнопка с топором.",
            reply_markup=confirm_clear_all_keyboard(),
        )
        return

    if data == "admin_clear_my_memory_do":
        clear_user_memory(query.from_user.id, query.message.chat.id)
        await query.edit_message_text("История этого чата очищена.", reply_markup=memory_keyboard())
        return

    if data == "admin_clear_all_memory_do":
        clear_all_memory()
        await query.edit_message_text("Вся история очищена.", reply_markup=memory_keyboard())
        return

    if data == "admin_show_global_memory":
        rows = list_memories("global")

        text = "\n".join([f"{k}: {v}" for k, v in rows]) if rows else "Глобальная память пуста."
        await query.edit_message_text(text[:3500], reply_markup=memory_keyboard())
        return

    if data == "admin_show_user_memory":
        rows = list_memories("user", query.from_user.id, query.message.chat.id)

        text = "\n".join([f"{k}: {v}" for k, v in rows]) if rows else "Память этого чата пуста."
        await query.edit_message_text(text[:3500], reply_markup=memory_keyboard())
        return

    await query.edit_message_text("Неизвестная кнопка. Видимо, кнопка тоже устала.", reply_markup=admin_keyboard())
