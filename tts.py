import os
import random
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY
from database import get_setting, set_setting


VOICE_MODES = ["off", "on", "random"]


def ensure_voice_defaults():
    if get_setting("voice_mode", None) is None:
        set_setting("voice_mode", "off")

    if get_setting("voice_chance", None) is None:
        set_setting("voice_chance", "25")

    if get_setting("tts_model", None) is None:
        set_setting("tts_model", "tts-1")

    if get_setting("tts_voice", None) is None:
        set_setting("tts_voice", "nova")


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


def get_voice_chance():
    ensure_voice_defaults()

    try:
        return min(100, max(0, int(get_setting("voice_chance", "25"))))
    except ValueError:
        return 25


def set_voice_chance(chance):
    chance = min(100, max(0, int(chance)))
    set_setting("voice_chance", str(chance))


def should_send_voice(answer):
    ensure_voice_defaults()
    mode = get_voice_mode()

    if mode == "off":
        return False

    if not answer or len(answer) > 900:
        return False

    if mode == "on":
        return True

    if mode == "random":
        return random.randint(1, 100) <= get_voice_chance()

    return False


def strip_for_tts(text):
    text = text or ""
    text = text.replace("* .. :) *", ".. улыбнулась.")
    text = text.replace(":)", "улыбка.")
    text = text.replace("*", "")
    return text.strip()[:900]


def convert_mp3_to_ogg(mp3_path):
    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        return None

    ogg_path = mp3_path.with_suffix(".ogg")

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(mp3_path),
        "-c:a",
        "libopus",
        "-b:a",
        "48k",
        str(ogg_path),
    ]

    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if result.returncode != 0 or not ogg_path.exists():
        return None

    return ogg_path


def make_tts_file(text):
    ensure_voice_defaults()

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is empty")

    clean_text = strip_for_tts(text)

    if not clean_text:
        raise RuntimeError("empty tts text")

    client = OpenAI(api_key=OPENAI_API_KEY)
    model = get_setting("tts_model", "tts-1")
    voice = get_setting("tts_voice", "nova")

    temp_dir = Path(tempfile.gettempdir())
    mp3_path = temp_dir / f"soiq_voice_{uuid.uuid4().hex}.mp3"

    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=clean_text,
    )

    # OpenAI SDK v1 supports stream_to_file for binary responses.
    response.stream_to_file(str(mp3_path))

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
