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
from personality import load_personality
from moods import mood_prompt
from memory import build_memory_prompt
from text_filters import need_detailed_answer, clean_answer, is_too_similar

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


def build_system_prompt(user_id, chat_id):
    memory_prompt = build_memory_prompt(user_id, chat_id)

    parts = [
        load_personality(),
        "НАСТРОЕНИЕ:\n" + mood_prompt(),
        "Стабильное ядро личности важнее настроения.",
    ]

    if memory_prompt:
        parts.append(memory_prompt)

    return "\n\n".join(parts)


def prepare_messages(user_id, chat_id, history, user_text, previous_answer=""):
    system_prompt = build_system_prompt(user_id, chat_id)

    messages = [{"role": "system", "content": system_prompt}]

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
        temperature=0.70,
        max_tokens=360,
    )

    return response.choices[0].message.content


def ask_openrouter_auto(messages):
    if not openrouter_client:
        raise RuntimeError("Нет OPENROUTER_API_KEY")

    response = openrouter_client.chat.completions.create(
        model=OPENROUTER_AUTO_MODEL,
        messages=messages,
        temperature=0.45,
        max_tokens=280,
    )

    return response.choices[0].message.content


def ask_groq(messages):
    if not groq_client:
        raise RuntimeError("Нет GROQ_API_KEY")

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.45,
        max_tokens=280,
    )

    return response.choices[0].message.content


def ask_openai(messages):
    if not openai_client:
        raise RuntimeError("Нет OPENAI_API_KEY")

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.45,
        max_tokens=280,
    )

    return response.choices[0].message.content


def provider_order(detailed):
    return [
        ("OpenRouter DeepSeek", ask_openrouter_deepseek),
        ("Groq", ask_groq),
        ("OpenRouter Auto", ask_openrouter_auto),
        ("OpenAI", ask_openai),
    ]

    return [
        ("Groq", ask_groq),
        ("OpenRouter DeepSeek", ask_openrouter_deepseek),
        ("OpenRouter Auto", ask_openrouter_auto),
        ("OpenAI", ask_openai),
    ]


def generate_answer(user_id, chat_id, user_text, history, previous_answer=""):
    detailed = need_detailed_answer(user_text)
    messages = prepare_messages(user_id, chat_id, history, user_text, previous_answer)

    last_error = None

    for name, provider in provider_order(detailed):
        try:
            print(f"Пробую: {name}")
            answer = provider(messages)

            if not answer:
                continue

            answer = clean_answer(answer, detailed=detailed)

            if previous_answer and is_too_similar(answer, previous_answer):
                print(f"{name} дал слишком похожий ответ, пробую дальше.")
                last_error = "too similar"
                continue

            return answer

        except Exception as error:
            print(f"{name} сломался:")
            print(error)
            last_error = error
            continue

    print("Последняя ошибка:", last_error)
    return "Все нейросети сейчас недоступны. Железный кружок по интересам развалился."
