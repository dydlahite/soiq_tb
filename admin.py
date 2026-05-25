from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database import cursor, get_setting, set_setting
from memory import clear_all_memory, clear_user_memory, count_messages, remember, forget, list_memories
from moods import MOODS, get_current_mood, set_mood_value, enable_auto_mood, disable_auto_mood
from media import add_media, list_media_categories, list_media_items, delete_media, set_media_chance, get_media_chance, get_random_media, send_media_item
from personality import load_personality, ensure_personality_file
from idle import get_idle_settings_text, set_idle_enabled, set_idle_hours, set_idle_chance, get_idle_hours, get_idle_chance
from tts import get_voice_mode, set_voice_mode, get_voice_chance, set_voice_chance, ensure_voice_defaults
from quotes import quote_status_text, get_quote_chance, set_quote_chance, get_quote_match_threshold, set_quote_match_threshold
from multimodal import set_voice_input, set_image_input, get_voice_input, get_image_input
from channel import (
    channel_status_text,
    set_channel_enabled,
    set_channel_hours,
    set_channel_chance,
    set_channel_mode,
    set_channel_format,
    clear_channel_recent,
)


STYLE_MODES = ["normal", "ornate", "messy", "dry", "angry", "soft"]


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


def keyboard(rows):
    return InlineKeyboardMarkup(rows)


def back_button():
    return [InlineKeyboardButton("Назад", callback_data="admin_main")]


def admin_keyboard():
    return keyboard([
        [InlineKeyboardButton("Статус", callback_data="admin_status"), InlineKeyboardButton("Debug", callback_data="admin_debug")],
        [InlineKeyboardButton("Настроение", callback_data="admin_mood_page"), InlineKeyboardButton("Режим речи", callback_data="admin_style_page")],
        [InlineKeyboardButton("Автонастроение", callback_data="admin_auto_mood_page"), InlineKeyboardButton("Автостиль", callback_data="admin_auto_style_page")],
        [InlineKeyboardButton("Платные/Groq", callback_data="admin_paid_page"), InlineKeyboardButton("Реакции", callback_data="admin_reactions_page")],
        [InlineKeyboardButton("Цитаты", callback_data="admin_quotes_page"), InlineKeyboardButton("Буфер/Reply", callback_data="admin_buffer_page")],
        [InlineKeyboardButton("Мультимодал", callback_data="admin_multimodal_page"), InlineKeyboardButton("Голос", callback_data="admin_voice_page")],
        [InlineKeyboardButton("Канал", callback_data="admin_channel_page"), InlineKeyboardButton("lowercase", callback_data="admin_lowercase_page")],
        [InlineKeyboardButton("Медиа", callback_data="admin_media_page")],
        [InlineKeyboardButton("Автосообщения", callback_data="admin_idle_page"), InlineKeyboardButton("Память", callback_data="admin_memory_page")],
        [InlineKeyboardButton("Помощь", callback_data="admin_help_page")],
    ])


def mood_keyboard():
    rows = [
        [InlineKeyboardButton("neutral", callback_data="admin_set_mood:neutral"), InlineKeyboardButton("tired", callback_data="admin_set_mood:tired")],
        [InlineKeyboardButton("cold", callback_data="admin_set_mood:cold"), InlineKeyboardButton("angry", callback_data="admin_set_mood:angry")],
        [InlineKeyboardButton("soft", callback_data="admin_set_mood:soft"), InlineKeyboardButton("playful", callback_data="admin_set_mood:playful")],
        [InlineKeyboardButton("romantic", callback_data="admin_set_mood:romantic"), InlineKeyboardButton("melancholic", callback_data="admin_set_mood:melancholic")],
        [InlineKeyboardButton("sarcastic", callback_data="admin_set_mood:sarcastic")],
        [InlineKeyboardButton("Авто ON", callback_data="admin_auto_mood:on"), InlineKeyboardButton("Авто OFF", callback_data="admin_auto_mood:off")],
        back_button(),
    ]
    return keyboard(rows)


def style_keyboard():
    return keyboard([
        [InlineKeyboardButton("normal", callback_data="admin_set_style:normal"), InlineKeyboardButton("ornate", callback_data="admin_set_style:ornate")],
        [InlineKeyboardButton("messy", callback_data="admin_set_style:messy"), InlineKeyboardButton("dry", callback_data="admin_set_style:dry")],
        [InlineKeyboardButton("angry", callback_data="admin_set_style:angry"), InlineKeyboardButton("soft", callback_data="admin_set_style:soft")],
        [InlineKeyboardButton("Автостиль ON", callback_data="admin_auto_style:on"), InlineKeyboardButton("Автостиль OFF", callback_data="admin_auto_style:off")],
        back_button(),
    ])


def lowercase_keyboard():
    return keyboard([[InlineKeyboardButton("off", callback_data="admin_lowercase:off"), InlineKeyboardButton("on", callback_data="admin_lowercase:on"), InlineKeyboardButton("random", callback_data="admin_lowercase:random")], back_button()])


def media_keyboard():
    return keyboard([
        [InlineKeyboardButton("0%", callback_data="admin_media_chance:0"), InlineKeyboardButton("10%", callback_data="admin_media_chance:10"), InlineKeyboardButton("20%", callback_data="admin_media_chance:20"), InlineKeyboardButton("35%", callback_data="admin_media_chance:35")],
        [InlineKeyboardButton("Список категорий", callback_data="admin_media_categories"), InlineKeyboardButton("Случайное медиа", callback_data="admin_send_random_media")],
        back_button(),
    ])


def idle_keyboard():
    return keyboard([
        [InlineKeyboardButton("idle ON", callback_data="admin_idle:on"), InlineKeyboardButton("idle OFF", callback_data="admin_idle:off")],
        [InlineKeyboardButton("6 ч", callback_data="admin_idle_hours:6"), InlineKeyboardButton("12 ч", callback_data="admin_idle_hours:12"), InlineKeyboardButton("24 ч", callback_data="admin_idle_hours:24"), InlineKeyboardButton("48 ч", callback_data="admin_idle_hours:48")],
        [InlineKeyboardButton("шанс 10%", callback_data="admin_idle_chance:10"), InlineKeyboardButton("шанс 30%", callback_data="admin_idle_chance:30"), InlineKeyboardButton("шанс 60%", callback_data="admin_idle_chance:60")],
        back_button(),
    ])


def voice_keyboard():
    return keyboard([
        [InlineKeyboardButton("voice off", callback_data="admin_voice_mode:off"), InlineKeyboardButton("voice on", callback_data="admin_voice_mode:on"), InlineKeyboardButton("voice random", callback_data="admin_voice_mode:random")],
        [InlineKeyboardButton("шанс 8%", callback_data="admin_voice_chance:8"), InlineKeyboardButton("шанс 12%", callback_data="admin_voice_chance:12"), InlineKeyboardButton("шанс 20%", callback_data="admin_voice_chance:20")],
        [InlineKeyboardButton("voice nova", callback_data="admin_tts_voice:nova"), InlineKeyboardButton("voice alloy", callback_data="admin_tts_voice:alloy"), InlineKeyboardButton("voice shimmer", callback_data="admin_tts_voice:shimmer")],
        back_button(),
    ])


def paid_keyboard():
    return keyboard([
        [InlineKeyboardButton("fallback ON", callback_data="admin_paid_fallback:on"), InlineKeyboardButton("fallback OFF", callback_data="admin_paid_fallback:off")],
        [InlineKeyboardButton("paid complex ON", callback_data="admin_paid_complex:on"), InlineKeyboardButton("paid complex OFF", callback_data="admin_paid_complex:off")],
        [InlineKeyboardButton("Groq ON", callback_data="admin_groq:on"), InlineKeyboardButton("Groq OFF", callback_data="admin_groq:off")],
        back_button(),
    ])


def reactions_keyboard():
    return keyboard([
        [InlineKeyboardButton("reactions ON", callback_data="admin_reactions:on"), InlineKeyboardButton("reactions OFF", callback_data="admin_reactions:off")],
        [InlineKeyboardButton("5%", callback_data="admin_reaction_chance:5"), InlineKeyboardButton("12%", callback_data="admin_reaction_chance:12"), InlineKeyboardButton("25%", callback_data="admin_reaction_chance:25"), InlineKeyboardButton("40%", callback_data="admin_reaction_chance:40")],
        back_button(),
    ])


def quotes_keyboard():
    return keyboard([
        [InlineKeyboardButton("quotes 0%", callback_data="admin_quote_chance:0"), InlineKeyboardButton("quotes 10%", callback_data="admin_quote_chance:10"), InlineKeyboardButton("quotes 18%", callback_data="admin_quote_chance:18"), InlineKeyboardButton("quotes 30%", callback_data="admin_quote_chance:30")],
        [InlineKeyboardButton("match 0.70", callback_data="admin_quote_match:0.70"), InlineKeyboardButton("match 0.78", callback_data="admin_quote_match:0.78"), InlineKeyboardButton("match 0.86", callback_data="admin_quote_match:0.86")],
        back_button(),
    ])


def buffer_keyboard():
    return keyboard([
        [InlineKeyboardButton("buffer ON", callback_data="admin_buffer:on"), InlineKeyboardButton("buffer OFF", callback_data="admin_buffer:off")],
        [InlineKeyboardButton("2 сек", callback_data="admin_buffer_seconds:2"), InlineKeyboardButton("4 сек", callback_data="admin_buffer_seconds:4"), InlineKeyboardButton("6 сек", callback_data="admin_buffer_seconds:6")],
        [InlineKeyboardButton("reply ON", callback_data="admin_reply_mode:on"), InlineKeyboardButton("reply random", callback_data="admin_reply_mode:random"), InlineKeyboardButton("reply OFF", callback_data="admin_reply_mode:off")],
        [InlineKeyboardButton("reply 8%", callback_data="admin_reply_chance:8"), InlineKeyboardButton("reply 18%", callback_data="admin_reply_chance:18"), InlineKeyboardButton("reply 30%", callback_data="admin_reply_chance:30")],
        back_button(),
    ])


def multimodal_keyboard():
    return keyboard([
        [InlineKeyboardButton("voice input ON", callback_data="admin_voice_input:on"), InlineKeyboardButton("voice input OFF", callback_data="admin_voice_input:off")],
        [InlineKeyboardButton("vision ON", callback_data="admin_image_input:on"), InlineKeyboardButton("vision OFF", callback_data="admin_image_input:off")],
        back_button(),
    ])



def channel_keyboard():
    return keyboard([
        [
            InlineKeyboardButton("channel ON", callback_data="admin_channel:on"),
            InlineKeyboardButton("channel OFF", callback_data="admin_channel:off"),
        ],
        [
            InlineKeyboardButton("6 ч", callback_data="admin_channel_hours:6"),
            InlineKeyboardButton("12 ч", callback_data="admin_channel_hours:12"),
            InlineKeyboardButton("24 ч", callback_data="admin_channel_hours:24"),
            InlineKeyboardButton("48 ч", callback_data="admin_channel_hours:48"),
        ],
        [
            InlineKeyboardButton("шанс 20%", callback_data="admin_channel_chance:20"),
            InlineKeyboardButton("шанс 35%", callback_data="admin_channel_chance:35"),
            InlineKeyboardButton("шанс 60%", callback_data="admin_channel_chance:60"),
        ],
        [
            InlineKeyboardButton("static", callback_data="admin_channel_mode:static"),
            InlineKeyboardButton("generated", callback_data="admin_channel_mode:generated"),
            InlineKeyboardButton("mixed", callback_data="admin_channel_mode:mixed"),
        ],
        [
            InlineKeyboardButton("diary", callback_data="admin_channel_format:diary"),
            InlineKeyboardButton("review", callback_data="admin_channel_format:review"),
            InlineKeyboardButton("format mixed", callback_data="admin_channel_format:mixed"),
        ],
        [InlineKeyboardButton("очистить повторы", callback_data="admin_channel_clear_recent")],
        back_button(),
    ])

def memory_keyboard():
    return keyboard([
        [InlineKeyboardButton("Очистить мой чат", callback_data="admin_clear_my_memory_confirm")],
        [InlineKeyboardButton("Очистить ВСЮ историю", callback_data="admin_clear_all_memory_confirm")],
        [InlineKeyboardButton("Глобальная память", callback_data="admin_show_global_memory"), InlineKeyboardButton("Память чата", callback_data="admin_show_user_memory")],
        back_button(),
    ])


def confirm_clear_my_keyboard():
    return keyboard([[InlineKeyboardButton("Да, очистить мой чат", callback_data="admin_clear_my_memory_do")], back_button()])


def confirm_clear_all_keyboard():
    return keyboard([[InlineKeyboardButton("Да, стереть ВСЮ историю", callback_data="admin_clear_all_memory_do")], back_button()])


def auto_mood_keyboard():
    return keyboard([[InlineKeyboardButton("Автонастроение ON", callback_data="admin_auto_mood:on"), InlineKeyboardButton("Автонастроение OFF", callback_data="admin_auto_mood:off")], back_button()])


def auto_style_keyboard():
    return keyboard([[InlineKeyboardButton("Автостиль ON", callback_data="admin_auto_style:on"), InlineKeyboardButton("Автостиль OFF", callback_data="admin_auto_style:off")], back_button()])


def status_text():
    ensure_voice_defaults()
    cursor.execute("SELECT COUNT(*) AS count FROM media")
    media_count = cursor.fetchone()["count"]
    return (
        f"Бот работает.\n"
        f"Настроение: {get_current_mood()}\n"
        f"Автонастроение: {get_setting('auto_mood', 'off')}\n"
        f"Режим речи: {get_setting('style_mode', 'normal')}\n"
        f"Провайдер: {get_setting('last_provider', 'нет')}\n"
        f"Groq: {get_setting('groq_enabled', 'off')}\n"
        f"paid fallback: {get_setting('paid_fallback', 'on')}\n"
        f"paid complex: {get_setting('paid_complex', 'off')}\n"
        f"reactions: {get_setting('reactions', 'on')} / {get_setting('reaction_chance', '12')}%\n"
        f"quotes: {get_quote_chance()}% / match {get_quote_match_threshold()}\n"
        f"buffer: {get_setting('message_buffer', 'on')} / {get_setting('message_buffer_seconds', '6')} сек\n"
        f"reply: {get_setting('reply_mode', 'random')} / {get_setting('reply_chance', '18')}%\n"
        f"voice input: {get_voice_input()} / image input: {get_image_input()}\n"
        f"voice: {get_voice_mode()} / {get_voice_chance()}% / {get_setting('tts_voice', 'nova')}\n"
        f"Сообщений в истории: {count_messages()}\n"
        f"Медиа: {media_count}\n"
        f"Шанс медиа: {get_media_chance()}%"
    )


def debug_text():
    ensure_voice_defaults()
    return (
        f"Провайдер последнего ответа: {get_setting('last_provider', 'нет')}\n"
        f"Последняя попытка провайдера: {get_setting('last_provider_try', 'нет')}\n"
        f"last complex: {get_setting('last_complex_message', 'нет')}\n"
        f"last paid complex: {get_setting('last_paid_complex', 'нет')}\n"
        f"last use expensive: {get_setting('last_use_expensive_model', 'нет')}\n"
        f"last prompt chars: {get_setting('last_prompt_chars', 'нет')}\n"
        f"Groq: {get_setting('groq_enabled', 'off')}\n"
        f"paid fallback: {get_setting('paid_fallback', 'on')}\n"
        f"paid complex: {get_setting('paid_complex', 'off')}\n"
        f"Настроение: {get_current_mood()}\n"
        f"Режим речи: {get_setting('style_mode', 'normal')}\n"
        f"lowercase: {get_setting('lowercase_mode', 'off')}\n"
        f"voice input: {get_voice_input()}\n"
        f"image input: {get_image_input()}\n"
        f"reactions: {get_setting('reactions', 'on')} / {get_setting('reaction_chance', '12')}%\n"
        f"quotes: {get_quote_chance()}% / match {get_quote_match_threshold()}\n"
        f"Сообщений в истории: {count_messages()}"
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой Telegram ID: {update.effective_user.id}")


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа. Какая дерзкая попытка.")
        return
    await update.message.reply_text("Админка. Теперь кнопок больше, потому что бот распух как шкаф с проводами.", reply_markup=admin_keyboard())


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text(
        "/admin - кнопочная панель\n/debug - режимы и провайдеры\n/status - статус\n"
        "/groq_on, /groq_off, /groq_status\n"
        "/paid_fallback_on, /paid_fallback_off, /paid_complex_on, /paid_complex_off\n"
        "/reactions, /set_reaction_chance 12\n/quotes, /set_quote_chance 18, /set_quote_match 0.78\n"
        "/buffer_on, /buffer_off, /set_buffer_seconds 2\n/reply_on, /reply_random, /reply_off, /set_reply_chance 18\n"
        "/voice_input_on, /voice_input_off, /vision_on, /vision_off"
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
        f"Режим речи: {get_setting('style_mode', 'normal')}\nПоследний режим: {get_setting('last_style_mode', 'normal')}\nАвторежим: {get_setting('auto_style', 'off')}\nДоступные: {', '.join(STYLE_MODES)}",
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
    await update.message.reply_text("lowercase random включен.")


async def reload_files_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("Файлы стиля будут перечитаны при следующем ответе.")


async def idle_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    set_idle_enabled(True)
    await update.message.reply_text("Автосообщения включены.")


async def idle_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    set_idle_enabled(False)
    await update.message.reply_text("Автосообщения выключены.")


async def set_idle_hours_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_idle_hours 24")
        return
    set_idle_hours(int(context.args[0]))
    await update.message.reply_text(f"Порог молчания: {get_idle_hours()} ч.")


async def set_idle_chance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_idle_chance 30")
        return
    set_idle_chance(int(context.args[0]))
    await update.message.reply_text(f"Шанс автосообщения: {get_idle_chance()}%")


async def voice_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    set_voice_mode("off")
    await update.message.reply_text("Голосовые выключены.")


async def voice_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    set_voice_mode("on")
    await update.message.reply_text("Голос разрешен, но не будет орать каждый раз.")


async def voice_random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    set_voice_mode("random")
    await update.message.reply_text(f"Голос random включен. Шанс: {get_voice_chance()}%")


async def set_voice_chance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("Нет доступа.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Пиши так: /set_voice_chance 25")
        return
    set_voice_chance(int(context.args[0]))
    await update.message.reply_text(f"Шанс голосового: {get_voice_chance()}%")


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
    await send_media_item(update.message, item)


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


def paid_text():
    return f"paid_fallback: {get_setting('paid_fallback', 'on')}\npaid_complex: {get_setting('paid_complex', 'off')}\nGroq: {get_setting('groq_enabled', 'off')}\nlast provider: {get_setting('last_provider', 'нет')}\nlast try: {get_setting('last_provider_try', 'нет')}"


def reactions_text():
    return f"reactions: {get_setting('reactions', 'on')}\nchance: {get_setting('reaction_chance', '12')}%\nПравила лежат в reaction_rules.txt."


def buffer_text():
    return f"message_buffer: {get_setting('message_buffer', 'on')}\nbuffer seconds: {get_setting('message_buffer_seconds', '6')}\nreply_mode: {get_setting('reply_mode', 'random')}\nreply_chance: {get_setting('reply_chance', '18')}%"


def multimodal_text():
    return f"voice input: {get_voice_input()}\nimage input: {get_image_input()}\nprovider: {get_setting('multimodal_provider', 'proxyapi')}\nlast multimodal provider: {get_setting('last_multimodal_provider', 'нет')}"


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        await query.edit_message_text("Нет доступа.")
        return
    data = query.data
    if data == "admin_main":
        await query.edit_message_text("Админка. Центр управления костылями.", reply_markup=admin_keyboard())
        return
    pages = {
        "admin_status": (status_text(), admin_keyboard()),
        "admin_debug": (debug_text(), admin_keyboard()),
        "admin_mood_page": (f"Настроение сейчас: {get_current_mood()}\nАвтонастроение: {get_setting('auto_mood', 'off')}", mood_keyboard()),
        "admin_style_page": (f"Режим речи: {get_setting('style_mode', 'normal')}\nАвторежим: {get_setting('auto_style', 'off')}", style_keyboard()),
        "admin_auto_mood_page": (f"Автонастроение: {get_setting('auto_mood', 'off')}", auto_mood_keyboard()),
        "admin_auto_style_page": (f"Авторежим речи: {get_setting('auto_style', 'off')}", auto_style_keyboard()),
        "admin_lowercase_page": (f"lowercase: {get_setting('lowercase_mode', 'off')}", lowercase_keyboard()),
        "admin_idle_page": (get_idle_settings_text(), idle_keyboard()),
        "admin_voice_page": (f"voice mode: {get_voice_mode()}\nvoice chance: {get_voice_chance()}%\ntts voice: {get_setting('tts_voice', 'nova')}", voice_keyboard()),
        "admin_media_page": (f"Шанс медиа: {get_media_chance()}%", media_keyboard()),
        "admin_memory_page": (f"Сообщений в истории: {count_messages()}", memory_keyboard()),
        "admin_paid_page": (paid_text(), paid_keyboard()),
        "admin_reactions_page": (reactions_text(), reactions_keyboard()),
        "admin_quotes_page": (quote_status_text(limit=8), quotes_keyboard()),
        "admin_buffer_page": (buffer_text(), buffer_keyboard()),
        "admin_multimodal_page": (multimodal_text(), multimodal_keyboard()),
        "admin_channel_page": (channel_status_text(), channel_keyboard()),
    }
    if data in pages:
        text, markup = pages[data]
        await query.edit_message_text(text[:3500], reply_markup=markup)
        return
    if data == "admin_help_page":
        await query.edit_message_text("Файлы руками:\npersonality.txt - личность\nspeech_markers.txt - условные речевые маркеры\nreaction_rules.txt - реакции\nquote_triggers.txt - цитаты/отсылки", reply_markup=admin_keyboard())
        return
    if data.startswith("admin_set_mood:"):
        mood = data.split(":", 1)[1]
        if mood in MOODS:
            set_mood_value(mood)
            await query.edit_message_text(f"Настроение установлено: {mood}", reply_markup=mood_keyboard())
        else:
            await query.edit_message_text("Нет такого настроения.", reply_markup=mood_keyboard())
        return
    if data.startswith("admin_auto_mood:"):
        value = data.split(":", 1)[1]
        if value == "on":
            enable_auto_mood()
        else:
            disable_auto_mood()
        await query.edit_message_text(f"Автонастроение: {get_setting('auto_mood', 'off')}", reply_markup=mood_keyboard())
        return
    if data.startswith("admin_set_style:"):
        mode = data.split(":", 1)[1]
        if mode in STYLE_MODES:
            set_setting("style_mode", mode)
            set_setting("auto_style", "off")
        await query.edit_message_text(f"Режим речи: {get_setting('style_mode', 'normal')}", reply_markup=style_keyboard())
        return
    if data.startswith("admin_auto_style:"):
        set_setting("auto_style", data.split(":", 1)[1])
        await query.edit_message_text(f"Авторежим речи: {get_setting('auto_style', 'off')}", reply_markup=style_keyboard())
        return
    if data.startswith("admin_lowercase:"):
        value = data.split(":", 1)[1]
        set_setting("lowercase_mode", value if value in ["on", "off", "random"] else "off")
        await query.edit_message_text(f"lowercase установлен: {get_setting('lowercase_mode', 'off')}", reply_markup=lowercase_keyboard())
        return
    if data.startswith("admin_idle:"):
        set_idle_enabled(data.split(":", 1)[1] == "on")
        await query.edit_message_text(get_idle_settings_text(), reply_markup=idle_keyboard())
        return
    if data.startswith("admin_idle_hours:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_idle_hours(int(value))
        await query.edit_message_text(get_idle_settings_text(), reply_markup=idle_keyboard())
        return
    if data.startswith("admin_idle_chance:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_idle_chance(int(value))
        await query.edit_message_text(get_idle_settings_text(), reply_markup=idle_keyboard())
        return
    if data.startswith("admin_voice_mode:"):
        set_voice_mode(data.split(":", 1)[1])
        await query.edit_message_text(f"voice mode: {get_voice_mode()}\nvoice chance: {get_voice_chance()}%", reply_markup=voice_keyboard())
        return
    if data.startswith("admin_voice_chance:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_voice_chance(int(value))
        await query.edit_message_text(f"voice chance: {get_voice_chance()}%", reply_markup=voice_keyboard())
        return
    if data.startswith("admin_tts_voice:"):
        set_setting("tts_voice", data.split(":", 1)[1])
        await query.edit_message_text(f"tts voice: {get_setting('tts_voice', 'nova')}", reply_markup=voice_keyboard())
        return
    if data.startswith("admin_media_chance:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_media_chance(int(value))
        await query.edit_message_text(f"Шанс медиа: {get_media_chance()}%", reply_markup=media_keyboard())
        return
    if data == "admin_media_categories":
        rows = list_media_categories()
        text = "Медиа нет." if not rows else "\n".join([f"{r['category']} / {r['media_type']}: {r['count']}" for r in rows])
        await query.edit_message_text(text[:3500], reply_markup=media_keyboard())
        return
    if data == "admin_send_random_media":
        item = get_random_media()
        if not item:
            await query.edit_message_text("Медиа нет.", reply_markup=media_keyboard())
            return
        await query.edit_message_text("Отправляю случайное медиа.", reply_markup=media_keyboard())
        await send_media_item(query.message, item)
        return
    if data.startswith("admin_paid_fallback:"):
        set_setting("paid_fallback", data.split(":", 1)[1])
        await query.edit_message_text(paid_text(), reply_markup=paid_keyboard())
        return
    if data.startswith("admin_paid_complex:"):
        set_setting("paid_complex", data.split(":", 1)[1])
        await query.edit_message_text(paid_text(), reply_markup=paid_keyboard())
        return
    if data.startswith("admin_groq:"):
        set_setting("groq_enabled", data.split(":", 1)[1])
        await query.edit_message_text(paid_text(), reply_markup=paid_keyboard())
        return
    if data.startswith("admin_reactions:"):
        set_setting("reactions", data.split(":", 1)[1])
        await query.edit_message_text(reactions_text(), reply_markup=reactions_keyboard())
        return
    if data.startswith("admin_reaction_chance:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_setting("reaction_chance", str(max(0, min(100, int(value)))))
        await query.edit_message_text(reactions_text(), reply_markup=reactions_keyboard())
        return
    if data.startswith("admin_quote_chance:"):
        set_quote_chance(data.split(":", 1)[1])
        await query.edit_message_text(quote_status_text(limit=8), reply_markup=quotes_keyboard())
        return
    if data.startswith("admin_quote_match:"):
        set_quote_match_threshold(data.split(":", 1)[1])
        await query.edit_message_text(quote_status_text(limit=8), reply_markup=quotes_keyboard())
        return
    if data.startswith("admin_buffer:"):
        set_setting("message_buffer", data.split(":", 1)[1])
        await query.edit_message_text(buffer_text(), reply_markup=buffer_keyboard())
        return
    if data.startswith("admin_buffer_seconds:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_setting("message_buffer_seconds", str(max(1, min(30, int(value)))))
        await query.edit_message_text(buffer_text(), reply_markup=buffer_keyboard())
        return
    if data.startswith("admin_reply_mode:"):
        value = data.split(":", 1)[1]
        set_setting("reply_mode", value if value in ["on", "off", "random"] else "random")
        await query.edit_message_text(buffer_text(), reply_markup=buffer_keyboard())
        return
    if data.startswith("admin_reply_chance:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_setting("reply_chance", str(max(0, min(100, int(value)))))
        await query.edit_message_text(buffer_text(), reply_markup=buffer_keyboard())
        return
    if data.startswith("admin_voice_input:"):
        set_voice_input(data.split(":", 1)[1] == "on")
        await query.edit_message_text(multimodal_text(), reply_markup=multimodal_keyboard())
        return
    if data.startswith("admin_image_input:"):
        set_image_input(data.split(":", 1)[1] == "on")
        await query.edit_message_text(multimodal_text(), reply_markup=multimodal_keyboard())
        return

    if data.startswith("admin_channel:"):
        set_channel_enabled(data.split(":", 1)[1] == "on")
        await query.edit_message_text(channel_status_text(), reply_markup=channel_keyboard())
        return

    if data.startswith("admin_channel_hours:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_channel_hours(int(value))
        await query.edit_message_text(channel_status_text(), reply_markup=channel_keyboard())
        return

    if data.startswith("admin_channel_chance:"):
        value = data.split(":", 1)[1]
        if value.isdigit():
            set_channel_chance(int(value))
        await query.edit_message_text(channel_status_text(), reply_markup=channel_keyboard())
        return

    if data.startswith("admin_channel_mode:"):
        set_channel_mode(data.split(":", 1)[1])
        await query.edit_message_text(channel_status_text(), reply_markup=channel_keyboard())
        return

    if data.startswith("admin_channel_format:"):
        set_channel_format(data.split(":", 1)[1])
        await query.edit_message_text(channel_status_text(), reply_markup=channel_keyboard())
        return

    if data == "admin_channel_clear_recent":
        clear_channel_recent()
        await query.edit_message_text("История повторов канала очищена. Ну вот, амнезия по расписанию.", reply_markup=channel_keyboard())
        return

    if data == "admin_clear_my_memory_confirm":
        await query.edit_message_text("Точно очистить историю этого чата?", reply_markup=confirm_clear_my_keyboard())
        return
    if data == "admin_clear_all_memory_confirm":
        await query.edit_message_text("Точно стереть ВСЮ историю сообщений? Это кнопка с топором.", reply_markup=confirm_clear_all_keyboard())
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
