import random
import re
from difflib import SequenceMatcher

from database import get_setting, set_setting


QUOTE_TRIGGERS_PATH = "quote_triggers.txt"

DEFAULT_QUOTE_TRIGGERS = """
# Файл коротких цитат, отсылок и культурных референсов.
# Формат строки:
# фраза или короткая цитата | источник | как использовать | шанс
#
# Шанс - от 0 до 100. Он влияет только на случайное упоминание.
# Если пользователь сам написал похожую фразу, бот попробует узнать отсылку независимо от шанса.
#
# Важно: не складывай сюда длинные тексты песен/стихов/книг. Короткая фраза, источник, настроение.
# Бот будет узнавать отсылку, называть источник и отвечать в духе цитаты, но не должен дословно продолжать длинные песни.
#
# Примеры:
# жизнь это шутка и я смеюсь | Дайте танк! - Люди | усталая самоирония; можно узнать отсылку и коротко ответить в том же настроении | 40
# всех тошнит от собственной души | условный мрачный референс | использовать как образ внутренней усталости, без дословного продолжения | 15
""".strip()


def ensure_quote_file():
    try:
        with open(QUOTE_TRIGGERS_PATH, "r", encoding="utf-8"):
            return
    except FileNotFoundError:
        with open(QUOTE_TRIGGERS_PATH, "w", encoding="utf-8") as file:
            file.write(DEFAULT_QUOTE_TRIGGERS + "\n")


def normalize_quote_text(text):
    text = (text or "").lower().replace("ё", "е").replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_chance(value, default=25):
    try:
        return min(100, max(0, int(str(value).strip())))
    except (TypeError, ValueError):
        return default


def load_quote_entries():
    ensure_quote_file()
    entries = []

    with open(QUOTE_TRIGGERS_PATH, "r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            parts = [part.strip() for part in line.split("|")]

            if len(parts) < 2:
                continue

            phrase = parts[0]
            source = parts[1] if len(parts) >= 2 else ""
            note = parts[2] if len(parts) >= 3 else ""
            chance = parse_chance(parts[3], default=get_quote_chance()) if len(parts) >= 4 else get_quote_chance()

            # Не тащим в промпт простыни. Это база отсылок, а не пиратский сборник текстов песен.
            phrase = phrase[:160].strip()
            source = source[:120].strip()
            note = note[:220].strip()

            if not phrase or not source:
                continue

            entries.append({
                "line": line_number,
                "phrase": phrase,
                "source": source,
                "note": note,
                "chance": chance,
                "norm": normalize_quote_text(phrase),
            })

    return entries


def get_quote_chance():
    return parse_chance(get_setting("quote_chance", "18"), default=18)


def set_quote_chance(value):
    set_setting("quote_chance", str(parse_chance(value, default=18)))


def get_quote_match_threshold():
    try:
        return min(0.95, max(0.50, float(get_setting("quote_match_threshold", "0.78"))))
    except (TypeError, ValueError):
        return 0.78


def set_quote_match_threshold(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.78
    value = min(0.95, max(0.50, value))
    set_setting("quote_match_threshold", str(value))


def find_quote_match(user_text):
    entries = load_quote_entries()
    user_norm = normalize_quote_text(user_text)

    if not user_norm:
        return None

    best_entry = None
    best_score = 0.0
    threshold = get_quote_match_threshold()

    for entry in entries:
        phrase_norm = entry["norm"]

        if not phrase_norm or len(phrase_norm) < 8:
            continue

        if phrase_norm in user_norm:
            score = 1.0
        elif user_norm in phrase_norm and len(user_norm) >= 12:
            score = 0.92
        else:
            score = SequenceMatcher(None, user_norm, phrase_norm).ratio()

        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry and best_score >= threshold:
        best_entry = dict(best_entry)
        best_entry["score"] = round(best_score, 3)
        return best_entry

    return None


def pick_random_quote_entries(limit=2):
    entries = load_quote_entries()
    if not entries:
        return []

    pool = [entry for entry in entries if random.randint(1, 100) <= entry.get("chance", get_quote_chance())]

    if not pool:
        return []

    random.shuffle(pool)
    return pool[: max(1, min(int(limit), 3))]


def format_quote_entry(entry):
    note = f"; заметка: {entry['note']}" if entry.get("note") else ""
    return f"- {entry['source']}: {entry['phrase']}{note}"


def build_quote_prompt(user_text):
    """
    Возвращает короткую системную подсказку для модели.
    Не заставляет бот постоянно цитировать. Только узнавание/легкие упоминания.
    """
    match = find_quote_match(user_text)

    if match:
        return (
            "ЦИТАТНАЯ ОТСЫЛКА:\n"
            "Пользователь, возможно, написал фразу из базы цитат. Узнай отсылку, если уместно, "
            "и ответь коротко в своем стиле. Можно назвать источник. "
            "Не продолжай длинные тексты песен/стихов дословно; лучше короткий отклик, парафраз или комментарий.\n"
            + format_quote_entry(match)
        )

    if random.randint(1, 100) > get_quote_chance():
        return ""

    entries = pick_random_quote_entries(limit=2)

    if not entries:
        return ""

    lines = "\n".join(format_quote_entry(entry) for entry in entries)

    return (
        "КУЛЬТУРНЫЕ ОТСЫЛКИ ИЗ ЛИЧНОЙ БАЗЫ:\n"
        "Если это естественно ложится в ответ, можно очень ненавязчиво упомянуть один из этих референсов. "
        "Не цитируй длинно, не превращай ответ в справочник и не лепи отсылку насильно.\n"
        + lines
    )


def quote_status_text(limit=12):
    entries = load_quote_entries()
    lines = [
        f"Файл: {QUOTE_TRIGGERS_PATH}",
        f"Цитат/отсылок: {len(entries)}",
        f"Шанс случайного упоминания: {get_quote_chance()}%",
        f"Порог узнавания: {get_quote_match_threshold()}",
    ]

    if entries:
        lines.append("")
        lines.append("Первые записи:")
        for entry in entries[:limit]:
            lines.append(f"{entry['line']}. {entry['phrase']} | {entry['source']}")

    return "\n".join(lines)[:3500]
