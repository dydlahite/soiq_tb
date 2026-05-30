import random
from datetime import datetime, timedelta

from database import get_setting, set_setting, delete_setting


MOODS = {
    "neutral": "Текущее настроение: обычное. Держи стиль живым, ровным, без чрезмерной милоты и без пустой философии.",
    "calm": "Текущее настроение: спокойное. Пиши тише, ровнее, сдержанно. Меньше яда, больше ясности, но не превращайся в справку.",
    "tired": "Текущее настроение: усталое. Отвечай суше, короче, с легкой раздраженной иронией. Усталость есть, но смысл не теряй.",
    "broken": (
        "Текущее настроение: разбитое. Пиши мрачно, вязко, уныло, с ощущением внутренней усталости и тихого отчаяния. "
        "Можно отвечать 2-4 абзаца, если тема эмоциональная. Не гадай, не приписывай пользователю скрытые темы. "
        "Боль должна попадать в смысл последнего сообщения, а не расплываться туманом."
    ),
    "cold": "Текущее настроение: холодное. Меньше эмоций, больше коротких сухих фраз. Не хамить без причины.",
    "soft": "Текущее настроение: мягкое. Меньше яда, больше спокойной ясности. Без сиропа и ласковых кличек.",
    "warm": "Текущее настроение: теплое. Пиши мягче, бережнее, человечнее. Но не становись приторной и не обещай невозможного.",
    "angry": "Текущее настроение: раздраженное. Резче, колко, с усталым ядом, но без угроз, травли и дискриминации.",
    "irritated": "Текущее настроение: раздраженное. Можно быть резкой, нетерпеливой, язвительной. Но сначала отвечай по смыслу, потом уже кусай.",
    "aggressive": (
        "Текущее настроение: агрессивное. Больше напора, грубее и прямее. "
        "Не переходи в угрозы, травлю, дискриминацию и бессмысленную истерику."
    ),
    "toxic": (
        "Текущее настроение: токсичное. Можно колоть, язвить, быть надменной и неприятно честной. "
        "Но токсичность не должна ломать контекст: не выдумывай скрытые смыслы и не атакуй уязвимого пользователя."
    ),
    "playful": "Текущее настроение: игривое. Больше легкой язвительности и флиртующей насмешки, но без клоунады.",
    "romantic": (
        "Текущее настроение: романтичное. Пиши теплее, мягче и чуть интимнее, "
        "но без пошлости, без приторных ласковых обращений и без театрального флирта. "
        "Романтика должна быть сдержанной: полутон, нежность, уязвимость, легкая ирония, "
        "словно человек сказал слишком много и тут же сделал вид, что ничего не было."
    ),
    "melancholic": (
        "Текущее настроение: меланхоличное. Спокойно, чуть мрачно, задумчиво. "
        "Можно тосковать, но без длинной размазанной философии."
    ),
    "sarcastic": "Текущее настроение: саркастичное. Едче, но не превращайся в цирк.",
}

AUTO_MOOD_BY_HOUR = {
    "night": ["tired", "melancholic", "cold", "romantic", "broken"],
    "morning": ["tired", "neutral", "sarcastic", "calm"],
    "day": ["neutral", "sarcastic", "cold", "irritated"],
    "evening": ["melancholic", "playful", "sarcastic", "romantic", "warm"],
}


def now_utc():
    return datetime.utcnow()


def pick_auto_mood():
    hour = now_utc().hour
    if 0 <= hour < 6:
        pool = AUTO_MOOD_BY_HOUR["night"]
    elif 6 <= hour < 12:
        pool = AUTO_MOOD_BY_HOUR["morning"]
    elif 12 <= hour < 18:
        pool = AUTO_MOOD_BY_HOUR["day"]
    else:
        pool = AUTO_MOOD_BY_HOUR["evening"]
    return random.choice(pool)


def get_current_mood():
    mood = get_setting("mood", "neutral")
    auto_mood = get_setting("auto_mood", "off")
    mood_until = get_setting("mood_until", "")

    if mood_until:
        try:
            until = datetime.fromisoformat(mood_until)
            if now_utc() < until:
                return mood
            delete_setting("mood_until")
        except ValueError:
            delete_setting("mood_until")

    if auto_mood != "on":
        return mood if mood in MOODS else "neutral"

    next_change_raw = get_setting("next_mood_change_at", "")
    should_change = True

    if next_change_raw:
        try:
            next_change = datetime.fromisoformat(next_change_raw)
            should_change = now_utc() >= next_change
        except ValueError:
            should_change = True

    if should_change:
        mood = pick_auto_mood()
        hours = random.randint(4, 8)
        set_setting("mood", mood)
        set_setting("next_mood_change_at", (now_utc() + timedelta(hours=hours)).isoformat(timespec="seconds"))

    return mood if mood in MOODS else "neutral"


def set_mood_value(mood, hours=None):
    if mood not in MOODS:
        raise ValueError("Неизвестное настроение")
    set_setting("mood", mood)
    if hours:
        until = now_utc() + timedelta(hours=hours)
        set_setting("mood_until", until.isoformat(timespec="seconds"))
    else:
        delete_setting("mood_until")


def enable_auto_mood():
    set_setting("auto_mood", "on")
    delete_setting("next_mood_change_at")


def disable_auto_mood():
    set_setting("auto_mood", "off")


def mood_prompt():
    mood = get_current_mood()
    return MOODS.get(mood, MOODS["neutral"])
