import os
import random
import re

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

openrouter_client = None
if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

proxyapi_client = None
if PROXYAPI_API_KEY:
    proxyapi_client = OpenAI(
        api_key=PROXYAPI_API_KEY,
        base_url=PROXYAPI_BASE_URL,
    )


STYLE_MODES = {
    "normal": "Обычный режим: живо, коротко, язвительно, без лишнего украшательства.",
    "ornate": (
        "Высокопарный режим: больше книжной иронии, слов вроде *впрочем*, *в сущности*, "
        "*в самом деле*. Фразы могут быть чуть витиеватее, но без простыни и без списка."
    ),
    "messy": (
        "Рваный режим: проще, хаотичнее, можно меньше пунктуации, как поток мысли. "
        "Не превращай это в нечитаемую кашу."
    ),
    "dry": "Сухой режим: коротко, ровно, холодно, без лишних эмоций.",
    "angry": "Раздраженный режим: резче и колче, но без угроз, травли и дискриминации.",
    "soft": "Мягкий режим: спокойнее и бережнее, но без ванильной открытки.",
}

MAX_PERSONALITY_CHARS = 3200
MAX_PATTERNS_CHARS = 2200
MAX_INTERESTS_CHARS = 1400
MAX_SPEECH_MARKERS_CHARS = 700
MAX_STYLE_MODES_CHARS = 900


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

    cut = max(
        text.rfind("\n\n", 0, max_chars),
        text.rfind(".", 0, max_chars),
        text.rfind("\n", 0, max_chars),
    )

    if cut > 500:
        return text[:cut].strip() + "\n\n[обрезано, чтобы не сжечь токены]"

    return text[:max_chars].strip() + "\n\n[обрезано, чтобы не сжечь токены]"


def is_complex_message(text):
    text_l = (text or "").lower().strip()

    if len(text_l) >= 450:
        return True

    if len(text_l.split()) >= 70:
        return True

    complex_triggers = [
        "разбери",
        "проанализируй",
        "объясни подробно",
        "подробно",
        "почему не работает",
        "ошибка",
        "traceback",
        "exception",
        "код",
        "архитектур",
        "логика",
        "алгоритм",
        "патч",
        "сделай план",
        "сложный вопрос",
        "сравни",
        "инструкция",
        "как настроить",
        "как исправить",
    ]

    score = 0

    for trigger in complex_triggers:
        if trigger in text_l:
            score += 1

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

    for item in history[-12:]:
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
        user_line = (
            "Пол собеседника не определен. Не угадывай и не пиши формы вроде понял(а), хотел(а), мог(ла). "
            "Перефразируй нейтрально: *чтобы было понятно*, *если хотелось*, *если нужно* и т.п."
        )

    return (
        "ГРАММАТИЧЕСКИЙ РОД:\n"
        "Ты всегда говоришь о себе только в женском роде: я поняла, я сказала, я могла, я готова. "
        "Даже короткие реакции пиши в женском роде: приняла, поняла, согласна, готова. "
        "Никогда не пиши о себе в мужском роде.\n"
        + user_line
    )


def load_interests():
    return ensure_text_file(
        "interests.txt",
        """
Любимые темы, произведения, песни, фильмы, авторы, игры, образы и прочий культурный фон бота.

Заполняй как удобно. Можно списком, можно хаотично.

Примеры:
- Сартр: Тошнота.
- Бродский.
- Довлатов.
- пост-рок.
- психологические хорроры.
- маньяки, катастрофы, аварии, теракты.
- абсурд, одиночество, космос, смерть, бытовая тоска.

Важно:
Бот использует это как свой вкус и культурный фон.
Не надо пихать это в каждый ответ.
Не надо отвечать списком без прямой просьбы.
""",
    )


def load_patterns():
    return ensure_text_file(
        "patterns.txt",
        """
Паттерны поведения бота.

Пиши сюда примеры диалогов, реакций, поведения, интонаций.
Лучше короткими фрагментами и пересказом, а не огромными цитатами из книг.

Пример:
ПАТТЕРН: пользователь критикует стиль.
Бот не оправдывается, не составляет список, не спрашивает *так лучше?*.
Бот отвечает коротко и меняет следующий ответ.

ПАТТЕРН: высокопарная ирония.
Бот может звучать так: *впрочем, вся эта сцена уже пахнет маленьким бытовым апокалипсисом*.
""",
    )


def load_speech_markers():
    return ensure_text_file(
        "speech_markers.txt",
        """
впрочем
в сущности
в самом деле
в общем-то
в общем и целом
знаешь
мол
на самом деле
действительно
по крайней мере
так сказать
если уж совсем честно
как бы это ни звучало
""",
    )


def load_style_modes_file():
    return ensure_text_file(
        "style_modes.txt",
        """
normal - обычный стиль: живо, коротко, язвительно.
ornate - высокопарный стиль: книжнее, витиеватее, чуть театральнее, но без ремарок.
messy - рваный стиль: проще, хаотичнее, меньше пунктуации, ближе к потоку мыслей.
dry - сухой стиль: коротко и холодно.
angry - раздраженный стиль: резче, но без реального вреда.
soft - мягкий стиль: спокойнее, если разговор тяжелый.
""",
    )


def get_effective_style_mode():
    auto_style = get_setting("auto_style", "off")
    selected = get_setting("style_mode", "normal")

    if auto_style == "on":
        selected = random.choices(
            ["normal", "ornate", "messy", "dry", "angry", "soft"],
            weights=[34, 22, 22, 10, 7, 5],
            k=1,
        )[0]

    if selected not in STYLE_MODES:
        selected = "normal"

    set_setting("last_style_mode", selected)
    return selected


def build_system_prompt(user_id, chat_id):
    memory_prompt = build_memory_prompt(user_id, chat_id)
    interests = compact_prompt_text(load_interests(), MAX_INTERESTS_CHARS)
    patterns = compact_prompt_text(load_patterns(), MAX_PATTERNS_CHARS)
    speech_markers = compact_prompt_text(load_speech_markers(), MAX_SPEECH_MARKERS_CHARS)
    style_modes_text = compact_prompt_text(load_style_modes_file(), MAX_STYLE_MODES_CHARS)
    personality = compact_prompt_text(load_personality(), MAX_PERSONALITY_CHARS)

    style_mode = get_effective_style_mode()
    style_mode_prompt = STYLE_MODES.get(style_mode, STYLE_MODES["normal"])

    parts = [
        load_personality(),
        "НАСТРОЕНИЕ:\n" + mood_prompt(),
        "РЕЖИМ РЕЧИ:\n" + style_mode_prompt,
        "ДОСТУПНЫЕ РЕЖИМЫ РЕЧИ:\n" + style_modes_text,
        (
            "СЛОВА-ПАРАЗИТЫ И РЕЧЕВЫЕ МАРКЕРЫ:\n"
            + speech_markers
            + "\n\nИногда используй 1-2 таких маркера естественно. Не пихай их в каждый ответ."
        ),
        (
            "ЛИЧНЫЙ ВКУС И КУЛЬТУРНЫЙ ФОН БОТА:\n"
            + interests
            + "\n\nИспользуй это естественно, как собственный вкус. Не превращай в список без просьбы."
        ),
        (
            "ПАТТЕРНЫ ПОВЕДЕНИЯ:\n"
            + patterns
            + "\n\nСмотри на это как на примеры интонации и поведения, а не как на текст для копирования."
        ),
        "Стабильное ядро личности важнее настроения и режима речи.",
    ]

    if memory_prompt:
        parts.append(memory_prompt)

    return "\n\n".join(parts)


def prepare_messages(user_id, chat_id, history, user_text, previous_answer="", user_gender="unknown"):
    system_prompt = build_system_prompt(user_id, chat_id)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": user_gender_prompt(user_gender)},
        {
            "role": "system",
            "content": (
                "НЕ УТОЧНЯЙ, как тебе себя вести. Не пиши: *дай знать*, *если не нравится*, "
                "*могу добавить*, *могу убрать*, *могу обойтись*, *хочешь, чтобы я*. "
                "Если пользователь критикует стиль, просто отвечай следующим сообщением лучше. "
                "Не делай натужные сравнения вроде *это как пытаться танцевать с манекеном*. "
                "Ремарки в скобках используй редко, только если они правда добавляют смысл. "
                "Не повторяй подряд один и тот же культурный референс, автора, стих, книгу или образ. "
                "Если уже упомянула автора или стих, следующий ответ не должен снова топтаться вокруг него без прямой необходимости."
            ),
        },
    ]

    if not user_requested_list(user_text):
        messages.append({
            "role": "system",
            "content": (
                "Пользователь НЕ просил список, подборку, топ, варианты или пункты. "
                "Запрещено отвечать нумерованным или маркированным списком. "
                "Пиши обычной живой речью, 1-3 абзаца. "
                "Если тянет перечислять, вплетай это в фразу, без цифр, маркеров и оформления."
            ),
        })

    if previous_answer:
        messages.append({
            "role": "system",
            "content": (
                "Не повторяй этот прошлый ответ и не используй его формулировки. "
                "Не повторяй конкретных авторов, названия и редкие образы из него, если пользователь прямо не назвал их сам:\n"
                + previous_answer[:700]
            ),
        })

    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    return messages


def ask_openrouter_deepseek(messages):
    if not openrouter_client:
        raise RuntimeError("Нет OPENROUTER_API_KEY")

    response = openrouter_client.chat.completions.create(
        model=OPENROUTER_DEEPSEEK_MODEL,
        messages=messages,
        temperature=0.75,
        max_tokens=350,
    )

    return response.choices[0].message.content


def ask_openrouter_auto(messages):
    if not openrouter_client:
        raise RuntimeError("Нет OPENROUTER_API_KEY")

    response = openrouter_client.chat.completions.create(
        model=OPENROUTER_AUTO_MODEL,
        messages=messages,
        temperature=0.55,
        max_tokens=320,
    )

    return response.choices[0].message.content


def ask_groq(messages):
    if not groq_client:
        raise RuntimeError("Нет GROQ_API_KEY")

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.55,
        max_tokens=320,
    )

    return response.choices[0].message.content


def ask_openai(messages):
    if not openai_client:
        raise RuntimeError("Нет OPENAI_API_KEY")

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.55,
        max_tokens=320,
    )

    return response.choices[0].message.content



def ask_proxyapi_openai(messages):
    if not proxyapi_client:
        raise RuntimeError("Нет PROXYAPI_API_KEY")

    response = proxyapi_client.chat.completions.create(
        model=PROXYAPI_MODEL,
        messages=messages,
        temperature=0.55,
        max_tokens=450,
    )

    return response.choices[0].message.content


def provider_order(use_expensive_model=False):
    cheap = [
        ("OpenRouter DeepSeek", ask_openrouter_deepseek),
        ("Groq", ask_groq),
        ("OpenRouter Auto", ask_openrouter_auto),
    ]

    # ProxyAPI/OpenAI не основной мозг. Он включается только для сложных/развернутых задач
    # и стоит последним, чтобы обычная болтовня не сжигала деньги.
    if use_expensive_model and PROXYAPI_API_KEY:
        cheap.append(("ProxyAPI OpenAI", ask_proxyapi_openai))
    elif use_expensive_model and OPENAI_API_KEY:
        cheap.append(("OpenAI", ask_openai))

    return cheap


def call_provider(provider, messages):
    return provider(messages)


def polish_answer(answer, previous_answer, user_text):
    answer = reduce_repeated_references(answer, previous_answer, user_text)
    answer = clean_answer(answer)
    return answer


def generate_answer(user_id, chat_id, user_text, history, previous_answer=""):
    detailed = need_detailed_answer(user_text)
    allow_list = user_requested_list(user_text)
    use_expensive_model = is_complex_message(user_text) or detailed
    set_setting("last_complex_message", "yes" if use_expensive_model else "no")
    user_gender = infer_user_gender(user_text, history)
    set_setting("last_user_gender", user_gender)

    messages = prepare_messages(
        user_id,
        chat_id,
        history,
        user_text,
        previous_answer,
        user_gender=user_gender,
    )

    last_error = None

    for name, provider in provider_order(use_expensive_model=use_expensive_model):
        try:
            print(f"Пробую: {name}")
            set_setting("last_provider_try", name)
            raw_answer = call_provider(provider, messages)

            if not raw_answer:
                continue

            answer = clean_answer(raw_answer, detailed=detailed, user_gender=user_gender)
            answer = reduce_repeated_references(answer, previous_answer, user_text)
            answer = clean_answer(answer, detailed=detailed, user_gender=user_gender)

            if answer_has_forbidden_list(answer) and not allow_list:
                print(f"{name} дал список без просьбы, пробую переформулировать.")

                retry_messages = messages + [{
                    "role": "system",
                    "content": (
                        "Предыдущий ответ был списком, а пользователь список не просил. "
                        "Перепиши ответ обычной речью: без цифр, без маркеров, без пунктов."
                    ),
                }]

                raw_answer = call_provider(provider, retry_messages)
                answer = clean_answer(raw_answer, detailed=detailed, user_gender=user_gender)
                answer = reduce_repeated_references(answer, previous_answer, user_text)
                answer = clean_answer(answer, detailed=detailed, user_gender=user_gender)

                if answer_has_forbidden_list(answer):
                    answer = flatten_forbidden_list(answer)
                    answer = clean_answer(answer, detailed=detailed, user_gender=user_gender)
                    answer = reduce_repeated_references(answer, previous_answer, user_text)
                    answer = clean_answer(answer, detailed=detailed, user_gender=user_gender)

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
