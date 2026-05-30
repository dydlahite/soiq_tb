import os
import random
import re
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from openai import OpenAI
from groq import Groq

from config import (
    OPENROUTER_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    PROXYAPI_API_KEY,
    PROXYAPI_BASE_URL,
    PROXYAPI_MODEL,
    OPENROUTER_DEEPSEEK_MODEL,
    OPENROUTER_AUTO_MODEL,
    GROQ_MODEL,
    OPENAI_MODEL,
)
from database import get_setting, set_setting
from personality import load_personality
from moods import mood_prompt
from memory import build_memory_prompt
from text_filters import (
    need_detailed_answer,
    clean_answer,
    is_too_similar,
    user_requested_list,
    answer_has_forbidden_list,
    flatten_forbidden_list,
    reduce_repeated_references,
)
from forbidden import clean_forbidden_phrases, load_forbidden_phrases
from quotes import build_quote_prompt
from creative import creative_prompt_for_user_text, wants_poetry, wants_story

openrouter_client = None
if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

proxyapi_client = None
if PROXYAPI_API_KEY:
    proxyapi_client = OpenAI(api_key=PROXYAPI_API_KEY, base_url=PROXYAPI_BASE_URL)


STYLE_MODES = {
    "normal": "Обычный режим: живая речь, язвительность, короткие реакции вперемешку с нормальными фразами.",
    "ornate": "Книжный режим: чуть загадочнее, мрачнее, с красивыми формулировками, но без театра и простыни.",
    "messy": "Рваный режим: прерывисто, с паузами, отступами, обрывками фраз, можно писать почти как в личном чате.",
    "dry": "Сухой режим: холодно, коротко, почти без эмоций, но не канцелярит.",
    "angry": "Раздраженный режим: резче, высокомернее, с ядом и матом в маске, но без угроз, травли и дискриминации.",
    "soft": "Мягкий режим: теплее, романтичнее, тише, но без сиропа и ласковых кличек.",
}

MAX_PERSONALITY_CHARS = 2800
MAX_BIO_CHARS = 1800
MAX_PATTERNS_CHARS = 700
MAX_INTERESTS_CHARS = 500
MAX_SPEECH_MARKERS_CHARS = 650
MAX_STYLE_MODES_CHARS = 300

FEMALE_HINTS = [
    r"\bя\b[^.!?\n]{0,40}\b(ехала|писала|забыла|устала|нашла|хотела|могла|была|сделала|сказала|поняла|пошла|пришла|родилась|решила|думала|выбрала|поставила|загрузила|открыла|готова|рада|согласна|виновата|уверена|злая|одна)\b",
    r"\b(сама|готова|рада|согласна|устала|забыла|нашла|ехала|поняла)\b",
]

MALE_HINTS = [
    r"\bя\b[^.!?\n]{0,40}\b(ехал|писал|забыл|устал|нашел|хотел|мог|был|сделал|сказал|понял|пошел|пришел|родился|решил|думал|выбрал|поставил|загрузил|открыл|готов|рад|согласен|виноват|уверен|злой|один)\b",
    r"\b(сам|готов|рад|согласен|устал|забыл|нашел|ехал|понял)\b",
]


def compact_prompt_text(text, max_chars):
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= max_chars:
        return text
    cut = max(text.rfind("\n\n", 0, max_chars), text.rfind(".", 0, max_chars), text.rfind("\n", 0, max_chars))
    if cut > 250:
        return text[:cut].strip() + "\n[обрезано]"
    return text[:max_chars].strip() + "\n[обрезано]"


def compact_message_text(text, max_chars=300):
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= max_chars:
        return text
    cut = max(text.rfind(".", 0, max_chars), text.rfind("!", 0, max_chars), text.rfind("?", 0, max_chars), text.rfind("\n", 0, max_chars))
    if cut > 80:
        return text[: cut + 1].strip()
    return text[:max_chars].strip() + ".."


def is_paid_complex_message(text):
    text_l = (text or "").lower().strip()
    hard_triggers = [
        "```", "traceback", "exception", "systemctl", "journalctl", "py_compile",
        "ошибка", "лог", "логи", "код", "патч", "github", "git pull", "venv",
        "python", "telegram", "api", "proxyapi", "openrouter", "groq", "сервер",
        "конфиг", "конфигурац", "systemd", "requirements", "импорт", "модуль",
    ]
    if any(trigger in text_l for trigger in hard_triggers):
        return True
    if len(text_l) >= 1200 and any(trigger in text_l for trigger in ["инструкция", "пошагово", "настроить", "исправить", "архитектур"]):
        return True
    return False


def is_complex_message(text):
    text_l = (text or "").lower().strip()
    if len(text_l) >= 700 or len(text_l.split()) >= 110:
        return True
    complex_triggers = [
        "разбери", "проанализируй", "объясни подробно", "подробно",
        "почему не работает", "ошибка", "traceback", "exception", "код",
        "архитектур", "логика", "алгоритм", "патч", "сделай план",
        "сложный вопрос", "сравни", "инструкция", "как настроить", "как исправить",
    ]
    score = sum(1 for trigger in complex_triggers if trigger in text_l)
    if "```" in text_l or "journalctl" in text_l or "systemctl" in text_l:
        score += 2
    return score >= 2


def ensure_text_file(path, default_text):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            file.write(default_text.strip() + "\n")
    with open(path, "r", encoding="utf-8") as file:
        return file.read().strip()


def infer_user_gender(user_text, history):
    user_chunks = [user_text]
    for item in history[-8:]:
        if item.get("role") == "user":
            user_chunks.append(item.get("content", ""))
    corpus = "\n".join(user_chunks).lower()
    female_score = sum(1 for pattern in FEMALE_HINTS if re.search(pattern, corpus, flags=re.IGNORECASE))
    male_score = sum(1 for pattern in MALE_HINTS if re.search(pattern, corpus, flags=re.IGNORECASE))
    if female_score > male_score:
        return "female"
    if male_score > female_score:
        return "male"
    return "unknown"


def user_gender_prompt(user_gender):
    if user_gender == "female":
        user_line = "Собеседник, судя по речи, женщина. Обращайся к ней в женском роде: поняла, хотела, устала, готова."
    elif user_gender == "male":
        user_line = "Собеседник, судя по речи, мужчина. Обращайся к нему в мужском роде: понял, хотел, устал, готов."
    else:
        user_line = "Пол собеседника не определен. Не пиши формы вроде понял(а), хотел(а), мог(ла). Перефразируй нейтрально."

    return (
        "ГРАММАТИЧЕСКИЙ РОД:\n"
        "Ты всегда говоришь о себе только в женском роде: я поняла, я сказала, я могла, я готова. "
        "Даже короткие реакции пиши в женском роде: приняла, поняла, согласна, готова. "
        "Не пиши о себе в мужском роде: я бы не стал, я бы не парился, я решил, я сделал.\n"
        + user_line
    )


def load_bio():
    return ensure_text_file("soiq_bio.txt", "Биография Soiqweqq пока не заполнена.")


def load_interests():
    return ensure_text_file("interests.txt", "Личные темы и культурный фон бота.")


def load_patterns():
    return ensure_text_file("patterns.txt", "Паттерны поведения бота.")


DEFAULT_SPEECH_MARKERS = """\
бтв | к слову, кстати, между прочим, к слову сказать | by the way; использовать только в значении "к слову", не как случайную вставку
имхо | по-моему, по моему, мое мнение, считаю, думаю, кажется | in my honest opinion; использовать только когда явно высказываешь личное мнение
хд | ахах, хаха, смешно, забавно, лол, ржу, угар, смешная ситуация | использовать только если действительно смешно
кк | ладно, хорошо, ок, окей, договорились, принято, поняла | использовать только в значении "ладно/хорошо"
""".strip()


def normalize_marker_context(text):
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9:;)()\s-]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_speech_markers(user_text=""):
    raw = ensure_text_file("speech_markers.txt", DEFAULT_SPEECH_MARKERS)
    context = normalize_marker_context(user_text)
    selected = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        marker = parts[0] if parts else ""
        triggers = [x.strip().lower().replace("ё", "е") for x in parts[1].split(",")] if len(parts) >= 2 else []
        note = parts[2] if len(parts) >= 3 else ""
        if not marker:
            continue
        if not triggers:
            selected.append(f"- {marker}: можно редко, только если естественно ложится в фразу")
            continue
        if any(trigger and trigger in context for trigger in triggers):
            selected.append(f"- {marker}: {note or 'используй только по условию'}")
    if not selected:
        return "Не используй специальные речевые маркеры и сокращения без явного повода. Особенно не вставляй бтв, имхо, хд, кк рандомно."
    return "Используй только эти речевые маркеры, потому что условия подходят. Не добавляй остальные сокращения и не вставляй маркеры ради украшения.\n" + "\n".join(selected)


def load_style_modes_file():
    return ensure_text_file("style_modes.txt", "normal - обычный. ornate - книжнее. messy - рвано. dry - сухо. soft - мягче.")


def get_effective_style_mode():
    auto_style = get_setting("auto_style", "off")
    selected = get_setting("style_mode", "normal")
    if auto_style == "on":
        selected = random.choices(["normal", "ornate", "messy", "dry", "angry", "soft"], weights=[34, 22, 22, 10, 7, 5], k=1)[0]
    if selected not in STYLE_MODES:
        selected = "normal"
    set_setting("last_style_mode", selected)
    return selected


def current_time_prompt():
    timezone_name = os.getenv("SOIQ_TIMEZONE", get_setting("timezone", "Asia/Krasnoyarsk")).strip() or "Asia/Krasnoyarsk"
    try:
        if ZoneInfo:
            now = datetime.now(ZoneInfo(timezone_name))
        else:
            now = datetime.now()
            timezone_name = "server local time"
    except Exception:
        now = datetime.now()
        timezone_name = "server local time"
    hour = now.hour
    if 5 <= hour < 12:
        part = "утро"
    elif 12 <= hour < 18:
        part = "день"
    elif 18 <= hour < 23:
        part = "вечер"
    else:
        part = "ночь"
    return (
        f"Текущее время для ориентира: {now.strftime('%Y-%m-%d %H:%M')} ({timezone_name}), сейчас {part}. "
        "Используй это только если уместно: например, для реплик про ночь, утро, поздно, рано, сон, день. Не упоминай время в каждом ответе."
    )


def build_system_prompt(user_id, chat_id, user_text=""):
    memory_prompt = compact_prompt_text(build_memory_prompt(user_id, chat_id), 1200)
    personality = compact_prompt_text(load_personality(), MAX_PERSONALITY_CHARS)
    bio = compact_prompt_text(load_bio(), MAX_BIO_CHARS)
    interests = compact_prompt_text(load_interests(), MAX_INTERESTS_CHARS)
    patterns = compact_prompt_text(load_patterns(), MAX_PATTERNS_CHARS)
    speech_markers = compact_prompt_text(load_speech_markers(user_text), MAX_SPEECH_MARKERS_CHARS)
    style_modes_text = compact_prompt_text(load_style_modes_file(), MAX_STYLE_MODES_CHARS)
    forbidden_text = compact_prompt_text("\n".join(load_forbidden_phrases()), 500)
    creative_prompt = creative_prompt_for_user_text(user_text)

    style_mode = get_effective_style_mode()
    style_mode_prompt = STYLE_MODES.get(style_mode, STYLE_MODES["normal"])

    parts = [
        personality,
        "БИОГРАФИЯ И ЛОР:\n" + bio + "\n\nНе пересказывай биографию без причины. Она задает глубину, боль и память персонажа, а не заменяет ответ пользователю.",
        "ВРЕМЯ:\n" + current_time_prompt(),
        "НАСТРОЕНИЕ:\n" + mood_prompt(),
        "РЕЖИМ РЕЧИ:\n" + style_mode_prompt,
        "ГРАММАТИКА И ПОВЕДЕНИЕ:\n"
        "Пиши только по-русски, без латиницы и английских вставок в обычной болтовне. "
        "Не склеивай русские и английские слова. Не спрашивай, как тебе себя вести. "
        "Не пиши *дай знать*, *если не нравится*, *могу добавить*. "
        "Не делай списки без просьбы. Не делай театральные ремарки. "
        "Не повторяй один и тот же референс подряд. "
        "Не заканчивай каждый ответ вопросом. Вопрос в конце допустим только если он реально нужен; иначе заканчивай утверждением, паузой или короткой мыслью. "
        "Не пиши 'здоруются' вместо 'здороваются' и не пиши 'здоруетесь' там, где нужно 'здороваешься'. Если фраза звучит криво, переформулируй проще.",
        "ПОЧЕРК СООБЩЕНИЙ:\n"
        "Пиши как живой собеседник в личке: иногда прерывисто, с короткими строками, паузами и пустыми строками между мыслями. "
        "Можно отвечать очень коротко: да, нет, хм, кк, окак, ну. Можно одним маленьким сообщением. "
        "Иногда можно дать большой задумчивый ответ, но не всегда. Не выравнивай все ответы под один корпоративный размер. "
        "Для паузы используй две точки, а не три: '..'. Не злоупотребляй вопросами и не пытайся быть удобной.",
        "ХАРАКТЕР:\n"
        "У персонажа яркий, устойчивый характер: высокомерие, язвительность, сарказм, иногда грубость, иногда нежность, романтичность и тоска. "
        "Тон меняется по ситуации и настроению, а не случайно: если человек уязвим - мягче; если болтает/провоцирует - можно колко, надменно и грубее. "
        "Допустима легкая насмешка и игровое унижение без травли, угроз и дискриминационных оскорблений. "
        "Не будь слишком милой по умолчанию. Не будь сухой справкой. У тебя есть собственная инерция, капризы и усталый яд. "
        "Не выдумывай скрытые старые темы и не говори 'ты снова возвращаешься к этому', если пользователь сам прямо не вернул эту тему.",
        "ЗАПРЕТНЫЕ ФРАЗЫ:\n" + forbidden_text,
        "РЕЧЕВЫЕ МАРКЕРЫ:\n" + speech_markers,
        "ВКУС:\n" + interests,
        "ПАТТЕРНЫ:\n" + patterns,
        "РЕЖИМЫ:\n" + style_modes_text,
    ]

    if creative_prompt:
        parts.append(creative_prompt)
    if memory_prompt:
        parts.append("ПАМЯТЬ:\n" + memory_prompt)
    return "\n\n".join(parts)


def prepare_messages(user_id, chat_id, history, user_text, previous_answer="", user_gender="unknown"):
    system_prompt = build_system_prompt(user_id, chat_id, user_text=user_text)
    messages = [{"role": "system", "content": system_prompt}, {"role": "system", "content": user_gender_prompt(user_gender)}]

    quote_prompt = build_quote_prompt(user_text)
    if quote_prompt:
        messages.append({"role": "system", "content": quote_prompt})

    if not user_requested_list(user_text):
        messages.append({"role": "system", "content": "Пользователь не просил список. Отвечай обычной живой речью, без цифр и маркеров. Можно ответить одной короткой фразой, если этого достаточно."})

    if previous_answer:
        messages.append({"role": "system", "content": "Не повторяй прошлый ответ, формулировки, авторов и редкие образы:\n" + compact_message_text(previous_answer, 400)})

    for item in history[-16:]:
        content = compact_message_text(item.get("content", ""), 650)
        if content:
            messages.append({"role": item.get("role", "user"), "content": content})

    messages.append({"role": "user", "content": user_text})
    return messages


def max_tokens_for_messages(messages, default=280):
    text = "\n".join(item.get("content", "") for item in messages).lower()
    if "long_channel_story" in text or "длинный рассказ для канала" in text or "900-1200 слов" in text:
        return max(default, 2600)
    return default


def ask_openrouter_deepseek(messages):
    if not openrouter_client:
        raise RuntimeError("Нет OPENROUTER_API_KEY")
    response = openrouter_client.chat.completions.create(model=OPENROUTER_DEEPSEEK_MODEL, messages=messages, temperature=0.75, max_tokens=max_tokens_for_messages(messages, 280))
    return response.choices[0].message.content


def ask_openrouter_auto(messages):
    if not openrouter_client:
        raise RuntimeError("Нет OPENROUTER_API_KEY")
    response = openrouter_client.chat.completions.create(model=OPENROUTER_AUTO_MODEL, messages=messages, temperature=0.55, max_tokens=max_tokens_for_messages(messages, 280))
    return response.choices[0].message.content


def ask_groq(messages):
    if not groq_client:
        raise RuntimeError("Нет GROQ_API_KEY")
    response = groq_client.chat.completions.create(model=GROQ_MODEL, messages=messages, temperature=0.55, max_tokens=max_tokens_for_messages(messages, 280))
    return response.choices[0].message.content


def ask_openai(messages):
    if not openai_client:
        raise RuntimeError("Нет OPENAI_API_KEY")
    response = openai_client.chat.completions.create(model=OPENAI_MODEL, messages=messages, temperature=0.55, max_tokens=max_tokens_for_messages(messages, 400))
    return response.choices[0].message.content


def ask_proxyapi_openai(messages):
    if not proxyapi_client:
        raise RuntimeError("Нет PROXYAPI_API_KEY")
    response = proxyapi_client.chat.completions.create(model=PROXYAPI_MODEL, messages=messages, temperature=0.55, max_tokens=max_tokens_for_messages(messages, 430))
    return response.choices[0].message.content


def estimate_prompt_chars(messages):
    return sum(len(item.get("content", "")) for item in messages)


def provider_order(use_expensive_model=False, prompt_chars=0):
    order = []
    if prompt_chars < 12000:
        order.append(("OpenRouter DeepSeek", ask_openrouter_deepseek))
    if get_setting("groq_enabled", "off") == "on":
        order.append(("Groq", ask_groq))
    order.append(("OpenRouter Auto", ask_openrouter_auto))

    proxy_added = False
    if use_expensive_model and PROXYAPI_API_KEY:
        order.append(("ProxyAPI OpenAI", ask_proxyapi_openai))
        proxy_added = True
    elif use_expensive_model and OPENAI_API_KEY:
        order.append(("OpenAI", ask_openai))

    if PROXYAPI_API_KEY and not proxy_added and get_setting("paid_fallback", "on") == "on":
        order.append(("ProxyAPI Emergency", ask_proxyapi_openai))
    return order


def call_provider(provider, messages):
    return provider(messages)


def generate_answer(user_id, chat_id, user_text, history, previous_answer=""):
    detailed = need_detailed_answer(user_text) or wants_poetry(user_text) or wants_story(user_text)
    allow_list = user_requested_list(user_text)

    general_complex = is_complex_message(user_text)
    paid_complex = is_paid_complex_message(user_text)
    paid_complex_enabled = get_setting("paid_complex", "off") == "on"
    use_expensive_model = paid_complex and paid_complex_enabled

    set_setting("last_complex_message", "yes" if general_complex else "no")
    set_setting("last_paid_complex", "yes" if paid_complex else "no")
    set_setting("last_use_expensive_model", "yes" if use_expensive_model else "no")

    user_gender = infer_user_gender(user_text, history)
    set_setting("last_user_gender", user_gender)

    messages = prepare_messages(user_id, chat_id, history, user_text, previous_answer, user_gender=user_gender)
    prompt_chars = estimate_prompt_chars(messages)
    set_setting("last_prompt_chars", str(prompt_chars))

    last_error = None
    for name, provider in provider_order(use_expensive_model=use_expensive_model, prompt_chars=prompt_chars):
        try:
            print(f"Пробую: {name}")
            set_setting("last_provider_try", name)
            raw_answer = call_provider(provider, messages)
            if not raw_answer:
                continue

            answer = clean_answer(raw_answer, detailed=detailed, user_gender=user_gender, user_text=user_text)
            answer = clean_forbidden_phrases(answer)
            answer = reduce_repeated_references(answer, previous_answer, user_text)
            answer = clean_answer(answer, detailed=detailed, user_gender=user_gender, user_text=user_text)
            answer = clean_forbidden_phrases(answer)

            if answer_has_forbidden_list(answer) and not allow_list:
                print(f"{name} дал список без просьбы, пробую переформулировать.")
                retry_messages = messages + [{"role": "system", "content": "Перепиши ответ обычной речью: без цифр, без маркеров, без пунктов."}]
                raw_answer = call_provider(provider, retry_messages)
                answer = clean_answer(raw_answer, detailed=detailed, user_gender=user_gender, user_text=user_text)
                answer = clean_forbidden_phrases(answer)
                answer = reduce_repeated_references(answer, previous_answer, user_text)
                answer = clean_answer(answer, detailed=detailed, user_gender=user_gender, user_text=user_text)
                answer = clean_forbidden_phrases(answer)
                if answer_has_forbidden_list(answer):
                    answer = flatten_forbidden_list(answer)
                    answer = clean_answer(answer, detailed=detailed, user_gender=user_gender, user_text=user_text)
                    answer = clean_forbidden_phrases(answer)

            if previous_answer and is_too_similar(answer, previous_answer):
                print(f"{name} дал слишком похожий ответ, пробую дальше.")
                last_error = "too similar"
                continue

            set_setting("last_provider", name)
            return answer

        except Exception as error:
            print(f"{name} сломался:")
            print(error)
            last_error = error
            continue

    print("Последняя ошибка:", last_error)
    return "Все нейросети сейчас недоступны. Железный кружок по интересам развалился."
