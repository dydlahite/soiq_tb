import os
import random
import re

from openai import OpenAI
from groq import Groq

from config import (
    OPENROUTER_API_KEY, GROQ_API_KEY, OPENAI_API_KEY,
    PROXYAPI_API_KEY, PROXYAPI_BASE_URL, PROXYAPI_MODEL,
    OPENROUTER_DEEPSEEK_MODEL, OPENROUTER_AUTO_MODEL, GROQ_MODEL, OPENAI_MODEL,
)
from database import get_setting, set_setting
from personality import load_personality
from moods import mood_prompt
from memory import build_memory_prompt
from text_filters import (
    need_detailed_answer, clean_answer, is_too_similar, user_requested_list,
    answer_has_forbidden_list, flatten_forbidden_list, reduce_repeated_references,
)

openrouter_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1") if OPENROUTER_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
proxyapi_client = OpenAI(api_key=PROXYAPI_API_KEY, base_url=PROXYAPI_BASE_URL) if PROXYAPI_API_KEY else None

STYLE_MODES = {
    "normal": "Обычный режим: живо, коротко, язвительно.",
    "ornate": "Книжнее и ироничнее, но без простыни и без списка.",
    "messy": "Рвано, проще, можно меньше пунктуации. Не превращай это в кашу.",
    "dry": "Коротко, ровно, холодно.",
    "angry": "Резче и колче, но без угроз, травли и дискриминации.",
    "soft": "Спокойнее и бережнее, но без ванильной открытки.",
}

FEMALE_HINTS = [
    r"\bя\b[^.!?\n]{0,40}\b(ехала|писала|забыла|устала|нашла|хотела|могла|была|сделала|сказала|поняла|пошла|пришла|родилась|решила|думала|выбрала|поставила|загрузила|открыла|готова|рада|согласна|виновата|уверена|злая|одна)\b",
    r"\b(сама|готова|рада|согласна|устала|забыла|нашла|ехала|поняла)\b",
]
MALE_HINTS = [
    r"\bя\b[^.!?\n]{0,40}\b(ехал|писал|забыл|устал|нашел|хотел|мог|был|сделал|сказал|понял|пошел|пришел|родился|решил|думал|выбрал|поставил|загрузил|открыл|готов|рад|согласен|виноват|уверен|злой|один)\b",
    r"\b(сам|готов|рад|согласен|устал|забыл|нашел|ехал|понял)\b",
]


def compact_text(text, max_chars):
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= max_chars:
        return text
    cut = max(text.rfind("\n\n", 0, max_chars), text.rfind(".", 0, max_chars), text.rfind("\n", 0, max_chars))
    if cut > 250:
        return text[:cut].strip() + "\n[обрезано]"
    return text[:max_chars].strip() + "\n[обрезано]"


def is_complex_message(text):
    text_l = (text or "").lower().strip()
    if len(text_l) >= 450 or len(text_l.split()) >= 70:
        return True
    triggers = ["разбери", "проанализируй", "объясни подробно", "подробно", "почему не работает", "ошибка", "traceback", "exception", "код", "архитектур", "логика", "алгоритм", "патч", "сделай план", "сложный вопрос", "сравни", "инструкция", "как настроить", "как исправить"]
    score = sum(1 for trigger in triggers if trigger in text_l)
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
    corpus = "\n".join([user_text] + [x.get("content", "") for x in history[-8:] if x.get("role") == "user"]).lower()
    female_score = sum(1 for pattern in FEMALE_HINTS if re.search(pattern, corpus, flags=re.IGNORECASE))
    male_score = sum(1 for pattern in MALE_HINTS if re.search(pattern, corpus, flags=re.IGNORECASE))
    if female_score > male_score:
        return "female"
    if male_score > female_score:
        return "male"
    return "unknown"


def user_gender_prompt(user_gender):
    if user_gender == "female":
        user_line = "Собеседник, судя по речи, женщина. Обращайся к ней в женском роде."
    elif user_gender == "male":
        user_line = "Собеседник, судя по речи, мужчина. Обращайся к нему в мужском роде."
    else:
        user_line = "Пол собеседника не определен. Не пиши формы вроде понял(а), хотел(а), мог(ла). Перефразируй нейтрально."
    return "ГРАММАТИЧЕСКИЙ РОД:\nТы всегда говоришь о себе только в женском роде: я поняла, я сказала, я могла, я готова. " + user_line


def load_interests():
    return ensure_text_file("interests.txt", "Личные темы и культурный фон бота.")


def load_patterns():
    return ensure_text_file("patterns.txt", "Паттерны поведения бота.")


def load_speech_markers():
    return ensure_text_file("speech_markers.txt", "впрочем\nв сущности\nзнаешь\nна самом деле\nпо крайней мере")


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


def build_system_prompt(user_id, chat_id):
    style_mode = get_effective_style_mode()
    parts = [
        compact_text(load_personality(), 1600),
        "НАСТРОЕНИЕ:\n" + mood_prompt(),
        "РЕЖИМ РЕЧИ:\n" + STYLE_MODES.get(style_mode, STYLE_MODES["normal"]),
        "ПРАВИЛА:\nНе спрашивай, как тебе себя вести. Не пиши *дай знать*, *если не нравится*, *могу добавить*. Не делай списки без просьбы. Не делай театральные ремарки. Не повторяй один и тот же референс подряд.",
        "МАРКЕРЫ:\n" + compact_text(load_speech_markers(), 300),
        "ВКУС:\n" + compact_text(load_interests(), 500),
        "ПАТТЕРНЫ:\n" + compact_text(load_patterns(), 700),
        "ПАМЯТЬ:\n" + compact_text(build_memory_prompt(user_id, chat_id), 700),
    ]
    return "\n\n".join([p for p in parts if p.strip()])


def prepare_messages(user_id, chat_id, history, user_text, previous_answer="", user_gender="unknown"):
    messages = [
        {"role": "system", "content": build_system_prompt(user_id, chat_id)},
        {"role": "system", "content": user_gender_prompt(user_gender)},
    ]
    if not user_requested_list(user_text):
        messages.append({"role": "system", "content": "Пользователь не просил список. Отвечай обычной живой речью, 1-3 абзаца, без цифр и маркеров."})
    if previous_answer:
        messages.append({"role": "system", "content": "Не повторяй прошлый ответ и редкие образы:\n" + compact_text(previous_answer, 250)})
    for item in history[-4:]:
        content = compact_text(item.get("content", ""), 300)
        if content:
            messages.append({"role": item.get("role", "user"), "content": content})
    messages.append({"role": "user", "content": user_text})
    return messages


def ask_openrouter_deepseek(messages):
    if not openrouter_client:
        raise RuntimeError("Нет OPENROUTER_API_KEY")
    response = openrouter_client.chat.completions.create(model=OPENROUTER_DEEPSEEK_MODEL, messages=messages, temperature=0.75, max_tokens=280)
    return response.choices[0].message.content


def ask_openrouter_auto(messages):
    if not openrouter_client:
        raise RuntimeError("Нет OPENROUTER_API_KEY")
    response = openrouter_client.chat.completions.create(model=OPENROUTER_AUTO_MODEL, messages=messages, temperature=0.55, max_tokens=280)
    return response.choices[0].message.content


def ask_groq(messages):
    if not groq_client:
        raise RuntimeError("Нет GROQ_API_KEY")
    response = groq_client.chat.completions.create(model=GROQ_MODEL, messages=messages, temperature=0.55, max_tokens=280)
    return response.choices[0].message.content


def ask_openai(messages):
    if not openai_client:
        raise RuntimeError("Нет OPENAI_API_KEY")
    response = openai_client.chat.completions.create(model=OPENAI_MODEL, messages=messages, temperature=0.55, max_tokens=400)
    return response.choices[0].message.content


def ask_proxyapi_openai(messages):
    if not proxyapi_client:
        raise RuntimeError("Нет PROXYAPI_API_KEY")
    response = proxyapi_client.chat.completions.create(model=PROXYAPI_MODEL, messages=messages, temperature=0.55, max_tokens=430)
    return response.choices[0].message.content


def prompt_chars(messages):
    return sum(len(item.get("content", "")) for item in messages)


def provider_order(use_expensive_model=False, chars=0):
    order = []
    if chars < 9000:
        order.append(("OpenRouter DeepSeek", ask_openrouter_deepseek))
    order.extend([("Groq", ask_groq), ("OpenRouter Auto", ask_openrouter_auto)])
    if use_expensive_model and PROXYAPI_API_KEY:
        order.append(("ProxyAPI OpenAI", ask_proxyapi_openai))
    elif use_expensive_model and OPENAI_API_KEY:
        order.append(("OpenAI", ask_openai))
    return order


def generate_answer(user_id, chat_id, user_text, history, previous_answer=""):
    detailed = need_detailed_answer(user_text)
    allow_list = user_requested_list(user_text)
    use_expensive_model = is_complex_message(user_text) or detailed
    set_setting("last_complex_message", "yes" if use_expensive_model else "no")
    user_gender = infer_user_gender(user_text, history)
    set_setting("last_user_gender", user_gender)
    messages = prepare_messages(user_id, chat_id, history, user_text, previous_answer, user_gender=user_gender)
    chars = prompt_chars(messages)
    set_setting("last_prompt_chars", str(chars))
    last_error = None
    for name, provider in provider_order(use_expensive_model=use_expensive_model, chars=chars):
        try:
            print(f"Пробую: {name}")
            set_setting("last_provider_try", name)
            raw_answer = provider(messages)
            if not raw_answer:
                continue
            answer = clean_answer(raw_answer, detailed=detailed, user_gender=user_gender)
            answer = reduce_repeated_references(answer, previous_answer, user_text)
            answer = clean_answer(answer, detailed=detailed, user_gender=user_gender)
            if answer_has_forbidden_list(answer) and not allow_list:
                raw_answer = provider(messages + [{"role": "system", "content": "Перепиши обычной речью без списка."}])
                answer = clean_answer(raw_answer, detailed=detailed, user_gender=user_gender)
                if answer_has_forbidden_list(answer):
                    answer = flatten_forbidden_list(answer)
                    answer = clean_answer(answer, detailed=detailed, user_gender=user_gender)
            if previous_answer and is_too_similar(answer, previous_answer):
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
