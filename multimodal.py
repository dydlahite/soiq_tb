import base64
from pathlib import Path

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    PROXYAPI_API_KEY,
    PROXYAPI_BASE_URL,
    MULTIMODAL_PROVIDER,
    STT_MODEL,
    VISION_MODEL,
)
from database import get_setting, set_setting


proxyapi_client = None
if PROXYAPI_API_KEY:
    proxyapi_client = OpenAI(api_key=PROXYAPI_API_KEY, base_url=PROXYAPI_BASE_URL)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_multimodal_client():
    provider = (get_setting("multimodal_provider", MULTIMODAL_PROVIDER) or "proxyapi").lower()

    if provider == "openai":
        if not openai_client:
            raise RuntimeError("Нет OPENAI_API_KEY для распознавания")
        return openai_client, "OpenAI"

    if proxyapi_client:
        return proxyapi_client, "ProxyAPI"

    if openai_client:
        return openai_client, "OpenAI"

    raise RuntimeError("Нет ключа для распознавания голосовых/картинок")


def set_voice_input(enabled: bool):
    set_setting("voice_input", "on" if enabled else "off")


def set_image_input(enabled: bool):
    set_setting("image_input", "on" if enabled else "off")


def get_voice_input():
    return get_setting("voice_input", "off")


def get_image_input():
    return get_setting("image_input", "off")


def transcribe_audio_file(path):
    client, provider_name = get_multimodal_client()
    with open(path, "rb") as file:
        response = client.audio.transcriptions.create(
            model=get_setting("stt_model", STT_MODEL),
            file=file,
        )

    set_setting("last_multimodal_provider", provider_name)
    text = getattr(response, "text", None) or str(response)
    return text.strip()


def image_to_data_url(path):
    suffix = Path(path).suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def describe_image_file(path, caption=""):
    client, provider_name = get_multimodal_client()
    caption = (caption or "").strip()

    prompt = (
        "Опиши картинку по-русски так, чтобы другой ИИ мог ответить пользователю. "
        "Не выдумывай личность людей на фото, не называй имена. "
        "Скажи, что видно, настроение, важные детали и текст на изображении, если он читается."
    )

    if caption:
        prompt += f"\nПодпись пользователя: {caption}"

    response = client.chat.completions.create(
        model=get_setting("vision_model", VISION_MODEL),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_to_data_url(path)}},
                ],
            }
        ],
        temperature=0.25,
        max_tokens=450,
    )

    set_setting("last_multimodal_provider", provider_name)
    return response.choices[0].message.content.strip()
