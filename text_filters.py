import re
from difflib import SequenceMatcher


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


def clean_answer(text, detailed=False):
    if not text:
        return ""

    text = text.replace("ё", "е").replace("Ё", "Е")

    text = re.sub(r"(?m)^\s*\*[^*\n]{1,200}\*\s*\n?", "", text)

    text = re.sub(
        r"\*(вздыхает|улыбается|смотрит[^*]*|молчит[^*]*|хмыкает[^*]*|сжимает[^*]*|отводит[^*]*|пожимает[^*]*)\*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = text.replace("**", "")

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

    max_len = 1100 if detailed else 450

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
            text = text[:max_len].strip() + "..."

    return text
