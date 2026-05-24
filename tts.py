import random
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    PROXYAPI_API_KEY,
    PROXYAPI_BASE_URL,
    PROXYAPI_TTS_MODEL,
    PROXYAPI_TTS_VOICE,
)
from database import get_setting, set_setting


VOICE_MODES = ["off", "on", "random"]


def ensure_voice_defaults():
    if get_setting("voice_mode", None) is None:
        set_setting("voice_mode", "off")

    if get_setting("voice_chance", None) is None:
        set_setting("voice_chance", "12")

    if get_setting("voice_max_per_day", None) is None:
        set_setting("voice_max_per_day", "2")

    if get_setting("voice_cooldown_hours", None) is None:
        set_setting("voice_cooldown_hours", "6")

    if get_setting("tts_model", None) is None:
        set_setting("tts_model", PROXYAPI_TTS_MODEL or "tts-1")

    if get_setting("tts_voice", None) is None:
        set_setting("tts_voice", PROXYAPI_TTS_VOICE or "nova")


def get_voice_mode():
    ensure_voice_defaults()
    mode = get_setting("voice_mode", "off")

    if mode not in VOICE_MODES:
        mode = "off"
        set_setting("voice_mode", mode)

    return mode


def set_voice_mode(mode):
    if mode not in VOICE_MODES:
        mode = "off"

    set_setting("voice_mode", mode)


def get_int_setting(key, default, min_value=0, max_value=100000):
    try:
        value = int(get_setting(key, str(default)))
    except ValueError:
        value = default

    return min(max_value, max(min_value, value))


def get_voice_chance():
    ensure_voice_defaults()
    return get_int_setting("voice_chance", 12, 0, 100)


def set_voice_chance(chance):
    chance = min(100, max(0, int(chance)))
    set_setting("voice_chance", str(chance))


def get_voice_max_per_day():
    ensure_voice_defaults()
    return get_int_setting("voice_max_per_day", 2, 0, 50)


def get_voice_cooldown_hours():
    ensure_voice_defaults()
    return get_int_setting("voice_cooldown_hours", 6, 0, 168)


def today_key():
    return datetime.utcnow().date().isoformat()


def get_voice_count_today():
    ensure_voice_defaults()

    current_date = get_setting("voice_count_date", "")

    if current_date != today_key():
        set_setting("voice_count_date", today_key())
        set_setting("voice_count_today", "0")
        return 0

    return get_int_setting("voice_count_today", 0, 0, 100000)


def record_voice_sent():
    ensure_voice_defaults()
    count = get_voice_count_today()
    set_setting("voice_count_today", str(count + 1))
    set_setting("last_voice_at", datetime.utcnow().isoformat(timespec="seconds"))


def parse_dt(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def voice_cooldown_passed():
    hours = get_voice_cooldown_hours()

    if hours <= 0:
        return True

    last_voice_at = parse_dt(get_setting("last_voice_at", ""))

    if not last_voice_at:
        return True

    return datetime.utcnow() - last_voice_at >= timedelta(hours=hours)


def can_send_voice():
    if get_voice_count_today() >= get_voice_max_per_day():
        return False

    if not voice_cooldown_passed():
        return False

    return True


def user_asks_voice(user_text):
    text_l = (user_text or "").lower()

    phrases = [
        "ответь голосом",
        "скинь голосовое",
        "запиши гс",
        "можешь голосом",
        "голосом ответь",
        "гс",
    ]

    return any(phrase in text_l for phrase in phrases)


def is_technical_text(text):
    text_l = (text or "").lower()

    technical_triggers = [
        "код", "ошибка", "traceback", "exception", "systemctl", "journalctl", "python",
        "api", "токен", "сервер", "github", "патч", "лог", "команда", "установи", "настрой",
    ]

    return any(trigger in text_l for trigger in technical_triggers)


def is_emotional_voice_moment(answer, user_text, mood=""):
    text_l = ((answer or "") + "\n" + (user_text or "") + "\n" + (mood or "")).lower()

    emotional_triggers = [
        "грустно", "печально", "тоскливо", "устала", "пусто", "жалко", "больно",
        "молч", "меланхол", "одиноч", "скуч", "* .. :) *", ".. :)",
    ]

    return any(trigger in text_l for trigger in emotional_triggers)


def should_send_voice(answer, user_text="", mood=""):
    ensure_voice_defaults()
    mode = get_voice_mode()

    if mode == "off":
        return False

    if not answer or len(answer) > 520:
        return False

    if is_technical_text(answer) or is_technical_text(user_text):
        return False

    if not can_send_voice():
        return False

    emotional = is_emotional_voice_moment(answer, user_text, mood)
    asked_voice = user_asks_voice(user_text)

    # Голос не команда и не банкоматная кнопка.
    # Просьба пользователя только повышает шанс, но не гарантирует отправку.
    if not emotional and not asked_voice:
        return False

    probability = get_voice_chance()

    if asked_voice:
        probability += 8

    if emotional:
        probability += 6

    probability = min(probability, 35)

    return random.randint(1, 100) <= probability


def strip_for_tts(text):
    text = text or ""
    text = text.replace("* .. :) *", "..")
    text = text.replace(":)", "")
    text = text.replace("*", "")
    return text.strip()[:520]


def make_tts_client():
    if PROXYAPI_API_KEY:
        return OpenAI(api_key=PROXYAPI_API_KEY, base_url=PROXYAPI_BASE_URL)

    if OPENAI_API_KEY:
        return OpenAI(api_key=OPENAI_API_KEY)

    raise RuntimeError("Нет PROXYAPI_API_KEY или OPENAI_API_KEY для TTS")


def convert_mp3_to_ogg(mp3_path):
    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        return None

    ogg_path = mp3_path.with_suffix(".ogg")
    command = [ffmpeg, "-y", "-i", str(mp3_path), "-c:a", "libopus", "-b:a", "48k", str(ogg_path)]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if result.returncode != 0 or not ogg_path.exists():
        return None

    return ogg_path


def write_speech_response(response, mp3_path):
    try:
        response.stream_to_file(str(mp3_path))
        return
    except AttributeError:
        pass

    with open(mp3_path, "wb") as file:
        file.write(response.read())


def make_tts_file(text):
    ensure_voice_defaults()
    clean_text = strip_for_tts(text)

    if not clean_text:
        raise RuntimeError("empty tts text")

    client = make_tts_client()
    model = get_setting("tts_model", PROXYAPI_TTS_MODEL or "tts-1")
    voice = get_setting("tts_voice", PROXYAPI_TTS_VOICE or "nova")

    temp_dir = Path(tempfile.gettempdir())
    mp3_path = temp_dir / f"soiq_voice_{uuid.uuid4().hex}.mp3"

    response = client.audio.speech.create(model=model, voice=voice, input=clean_text)
    write_speech_response(response, mp3_path)

    ogg_path = convert_mp3_to_ogg(mp3_path)

    if ogg_path:
        try:
            mp3_path.unlink(missing_ok=True)
        except Exception:
            pass
        return ogg_path, True

    return mp3_path, False


def cleanup_voice_file(path):
    try:
        if path:
            Path(path).unlink(missing_ok=True)
    except Exception:
        pass
