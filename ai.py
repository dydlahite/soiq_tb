import os
import random

from openai import OpenAI
from groq import Groq

from config import (
    OPENROUTER_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
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


def ensure_text_file(path, default_text):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            file.write(default_text.strip() + "\n")

    with open(path, "r", encoding="utf-8") as file:
        return file.read().strip()


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
normal — обычный стиль: живо, коротко, язвительно.
ornate — высокопарный стиль: книжнее, витиеватее, чуть театральнее, но без ремарок.
messy — рваный стиль: проще, хаотичнее, меньше пунктуации, ближе к потоку мыслей.
dry — сухой стиль: коротко и холодно.
angry — раздраженный стиль: резче, но без реального вреда.
soft — мягкий стиль: спокойнее, если разговор тяжелый.
""",
    )


def get_effective_style_mode():
    auto_style = get_setting("auto_style", "off")
    selected = get_setting("style_mode", "normal")

    if auto_style == "on":
        # Не слишком часто мягкий/злой, чаще normal/ornate/messy.
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
    interests = load_interests()
    patterns = load_patterns()
    speech_markers = load_speech_markers()
    style_modes_text = load_style_modes_file()

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


def prepare_messages(user_id, chat_id, history, user_text, previous_answer=""):
    system_prompt = build_system_prompt(user_id, chat_id)

    messages = [{"role": "system", "content": system_prompt}]

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
            "content": "Не повторяй этот прошлый ответ и не используй его формулировки:\n" + previous_answer[:700],
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


def provider_order(detailed):
    return [
        ("OpenRouter DeepSeek", ask_openrouter_deepseek),
        ("Groq", ask_groq),
        ("OpenRouter Auto", ask_openrouter_auto),
        ("OpenAI", ask_openai),
    ]


def call_provider(provider, messages):
    return provider(messages)


def generate_answer(user_id, chat_id, user_text, history, previous_answer=""):
    detailed = need_detailed_answer(user_text)
    allow_list = user_requested_list(user_text)
    messages = prepare_messages(user_id, chat_id, history, user_text, previous_answer)

    last_error = None

    for name, provider in provider_order(detailed):
        try:
            print(f"Пробую: {name}")
            set_setting("last_provider_try", name)
            raw_answer = call_provider(provider, messages)

            if not raw_answer:
                continue

            answer = clean_answer(raw_answer, detailed=detailed)

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
                answer = clean_answer(raw_answer, detailed=detailed)

                if answer_has_forbidden_list(answer):
                    answer = flatten_forbidden_list(answer)
                    answer = clean_answer(answer, detailed=detailed)

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
