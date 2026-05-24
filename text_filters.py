import random
import re
from difflib import SequenceMatcher

from database import get_setting


def need_detailed_answer(text):
    text_lower = text.lower()

    keywords = [
        "подробно",
        "объясни",
        "распиши",
        "почему",
        "как работает",
        "проанализируй",
        "сравни",
        "пошагово",
        "инструкция",
        "план",
    ]

    if len(text) > 250:
        return True

    return any(word in text_lower for word in keywords)


def user_requested_list(text):
    text_lower = text.lower()

    triggers = [
        "список",
        "списком",
        "перечисли",
        "подборк",
        "топ",
        "варианты",
        "вариантов",
        "пункты",
        "по пунктам",
        "пошагово",
        "по шагам",
        "команды",
        "что посмотреть",
        "что почитать",
        "что послушать",
    ]

    return any(trigger in text_lower for trigger in triggers)


def answer_has_forbidden_list(text):
    if not text:
        return False

    numbered = re.findall(r"(?m)^\s*\d+[.)]\s+", text)
    bullets = re.findall(r"(?m)^\s*[-•]\s+", text)

    return len(numbered) >= 2 or len(bullets) >= 2


def flatten_forbidden_list(text):
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        line = re.sub(r"^\s*\d+[.)]\s*", "", line)
        line = re.sub(r"^\s*[-•]\s*", "", line)
        line = line.strip()

        if line:
            cleaned.append(line)

    result = " ".join(cleaned)
    result = re.sub(r"\s{2,}", " ", result)
    return result.strip()


def normalize_for_compare(text):
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\wа-яА-Я ]+", "", text)
    return text.strip()


def is_too_similar(a, b, threshold=0.72):
    if not a or not b:
        return False

    a = normalize_for_compare(a)
    b = normalize_for_compare(b)

    if len(a) < 20 or len(b) < 20:
        return False

    return SequenceMatcher(None, a, b).ratio() >= threshold


def replace_quotes_with_stars(text):
    quote_pairs = [
        (r"«\s*([^»\n]{1,220}?)\s*»", r"*\1*"),
        (r"„\s*([^“\n]{1,220}?)\s*“", r"*\1*"),
        (r"“\s*([^”\n]{1,220}?)\s*”", r"*\1*"),
        (r"”\s*([^”\n]{1,220}?)\s*”", r"*\1*"),
        (r"<<\s*([^>\n]{1,220}?)\s*>>", r"*\1*"),
        (r"\"\s*([^\"\n]{1,220}?)\s*\"", r"*\1*"),
    ]

    for pattern, replacement in quote_pairs:
        text = re.sub(pattern, replacement, text)

    # markdown-жирность вокруг фразы превращаем в одиночные звезды.
    # Мат внутри слова не трогаем.
    text = re.sub(r"(?<!\w)\*\*([^*\n]{1,220}?)\*\*(?!\w)", r"*\1*", text)

    text = text.replace("«", "*").replace("»", "*")
    text = text.replace("“", "*").replace("”", "*").replace("„", "*")
    text = text.replace("<<", "*").replace(">>", "*")
    text = text.replace('"', "*")

    return text


def normalize_punctuation(text):
    # Нейросетевые длинные тире режем в обычный дефис.
    text = text.replace("—", "-").replace("–", "-").replace("−", "-")

    # Один символ многоточия и любые 3+ точки превращаем в две точки.
    text = text.replace("…", "..")
    text = re.sub(r"\.{3,}", "..", text)

    # Если модель делает уродство вроде ". ." или ".. .", приводим к двум точкам.
    text = re.sub(r"\.\s+\.", "..", text)
    text = re.sub(r"\.\.\s+\.", "..", text)

    return text


def maybe_add_sad_pause(text):
    if not text:
        return text

    stripped = text.strip()

    if stripped.endswith(":)") or stripped.endswith(".. :)"):
        return text

    lower = stripped.lower()

    sad_words = [
        "грустно",
        "печально",
        "тоскливо",
        "жалко",
        "больно",
        "пусто",
        "устала",
        "устал",
        "одиноч",
        "мертв",
        "смерт",
        "болото",
        "бессмысленно",
        "ничего не меняется",
    ]

    # Короткий ответ, где как будто нечего сказать.
    short_empty_answer = len(stripped) <= 80 and random.randint(1, 100) <= 14

    # Грустный контекст, но тоже не в каждый раз, иначе это будет не стиль, а тремор.
    sad_context = any(word in lower for word in sad_words) and random.randint(1, 100) <= 22

    if short_empty_answer or sad_context:
        if stripped.endswith("."):
            stripped = stripped[:-1].rstrip()

        stripped += ".. :)"

    return stripped


def apply_lowercase_mode(text):
    mode = get_setting("lowercase_mode", "off")

    if mode == "on":
        return text.lower()

    if mode == "random" and random.randint(1, 100) <= 35:
        return text.lower()

    return text


def clean_answer(text, detailed=False):
    if not text:
        return ""

    text = text.replace("ё", "е").replace("Ё", "Е")
    text = replace_quotes_with_stars(text)
    text = normalize_punctuation(text)

    # Ролевые действия отдельными строками: *вздыхает*, *молчит*.
    text = re.sub(r"(?m)^\s*\*[^*\n]{1,200}\*\s*\n?", "", text)

    # Театральные ремарки внутри текста.
    text = re.sub(
        r"\*(вздыхает|улыбается|смотрит[^*]*|молчит[^*]*|хмыкает[^*]*|сжимает[^*]*|отводит[^*]*|пожимает[^*]*)\*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    bad_phrases = [
        "Теперь лучше?",
        "Так лучше?",
        "Вот тебе ядовитый ответ:",
        "Вот ядовитый ответ:",
        "Ладно, держи краткий чек-лист",
        "держи краткий чек-лист",
        "чек-лист для будущего редактирования",
        "Может, я слишком",
        "Может, ты слишком",
        "Ты сама меня такой сделала",
        "Так что теперь терпи",
        "милый пирожочек",
        "солнышко мое",
        "солнышко",
        "зай",
        "милая",
        "дорогая",
        "детка",
        "хочешь, чтобы я стала проще",
        "если хочешь пофлиртовать",
        "расскажи мне",
        "опиши мне",
    ]

    for phrase in bad_phrases:
        text = text.replace(phrase, "")

    protected_slur_patterns = [
        r"\bчурк\w*\b",
    ]

    for pattern in protected_slur_patterns:
        text = re.sub(pattern, "[вырезано]", text, flags=re.IGNORECASE)

    replacements = {
        r"\bбля\b": "б*я",
        r"\bблять\b": "бл*ть",
        r"\bпиздец\b": "п*здец",
        r"\bпизда\b": "п*зда",
        r"\bпизду\b": "п*зду",
        r"\bпиздишь\b": "п*здишь",
        r"\bхуй\b": "х*й",
        r"\bхуя\b": "х*я",
        r"\bхуево\b": "х*ево",
        r"\bебать\b": "е*ать",
        r"\bебаный\b": "е*аный",
        r"\bебанная\b": "е*анная",
        r"\bзаебала\b": "за*бала",
        r"\bзаебал\b": "за*бал",
        r"\bсука\b": "с*ка",
    }

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"\bпдец\b", "п*здец", text, flags=re.IGNORECASE)
    text = re.sub(r"\bбя\b", "б*я", text, flags=re.IGNORECASE)

    if text.count(":)") > 1:
        text = text.replace(":)", "", text.count(":)") - 1)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    max_len = 1300 if detailed else 650

    if len(text) > max_len:
        cut_positions = [
            text.rfind(".", 0, max_len),
            text.rfind("!", 0, max_len),
            text.rfind("?", 0, max_len),
            text.rfind("\n", 0, max_len),
        ]

        cut = max(cut_positions)

        if cut > 180:
            text = text[: cut + 1].strip()
        else:
            text = text[:max_len].strip() + ".."

    text = maybe_add_sad_pause(text)
    text = normalize_punctuation(text)
    text = apply_lowercase_mode(text)

    return text
