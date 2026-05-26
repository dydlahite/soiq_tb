import random
import re
from difflib import SequenceMatcher

from database import get_setting

SHORT_BARE_REPLIES = {
    "да", "нет", "хм", "мда", "ну", "ок", "кк", "окак", "ага", "угу", "неа", "ладно",
    "приняла", "поняла", "ясно", "бывает", "увы", "что ж", "пожалуй",
}


def is_short_bare_reply_text(text):
    return (text or "").strip().lower().replace(".", "") in SHORT_BARE_REPLIES


def need_detailed_answer(text):
    text_lower = text.lower()

    keywords = [
        "подробно", "объясни", "распиши", "почему", "как работает",
        "проанализируй", "сравни", "пошагово", "инструкция", "план",
    ]

    if len(text) > 250:
        return True

    return any(word in text_lower for word in keywords)


def user_requested_list(text):
    text_lower = text.lower()

    triggers = [
        "список", "списком", "перечисли", "подборк", "топ",
        "варианты", "вариантов", "пункты", "по пунктам",
        "пошагово", "по шагам", "команды", "что посмотреть",
        "что почитать", "что послушать",
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


def split_to_sentences(text):
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


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
    text = re.sub(r"(?<!\w)\*\*([^*\n]{1,220}?)\*\*(?!\w)", r"*\1*", text)
    text = text.replace("«", "*").replace("»", "*")
    text = text.replace("“", "*").replace("”", "*").replace("„", "*")
    text = text.replace("<<", "*").replace(">>", "*")
    text = text.replace('"', "*")
    return text


def normalize_punctuation(text):
    text = text.replace("—", "-").replace("–", "-").replace("−", "-")
    text = text.replace("…", "..")
    text = re.sub(r"\.{3,}", "..", text)
    text = re.sub(r"\.\s+\.", "..", text)
    text = re.sub(r"\.\.\s+\.", "..", text)
    text = re.sub(r",\s*([.!?])", r"\1", text)
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"([;:])\s*\1+", r"\1", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])\s+([,.!?;:])", r"\1\2", text)
    text = re.sub(r",\s*([.!?])", r"\1", text)
    text = re.sub(r"([.!?])[,;:]+", r"\1", text)
    text = re.sub(r"\?\s*\.", "?", text)
    text = re.sub(r"!\s*\.", "!", text)
    return text


def fix_mixed_english_artifacts(text, detailed=False):
    if not text:
        return text

    replacements = {
        r"(?i)(?<=[а-яё])recentно": " недавно",
        r"(?i)\brecentно\b": "недавно",
        r"(?i)\brecently\b": "недавно",
        r"(?i)(?<=[а-яё])randomно": " случайно",
        r"(?i)\brandomно\b": "случайно",
        r"(?i)\bactually\b": "на самом деле",
        r"(?i)\bbtw\b": "кстати",
        r"(?i)\bokay\b": "ок",
        r"(?i)\bok\b": "ок",
    }

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)

    if not detailed:
        text = re.sub(r"(?<=[а-яА-Я])\s*[A-Za-z]{2,}\s*(?=[а-яА-Я])", " ", text)
        allowed_words = {"openai", "proxyapi", "deepseek", "github", "groq", "tts", "api", "telegram", "python", "systemd", "openrouter"}

        def remove_lonely_latin(match):
            word = match.group(0)
            return word if word.lower() in allowed_words else ""

        text = re.sub(r"\b[A-Za-z]{2,}\b", remove_lonely_latin, text)

    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return text.strip()


def fix_bot_self_gender(text):
    replacements = {
        r"\bя не понял\b": "я не поняла", r"\bя понял\b": "я поняла",
        r"\bя принял\b": "я приняла", r"\bя готов\b": "я готова",
        r"\bя рад\b": "я рада", r"\bя согласен\b": "я согласна",
        r"\bя уверен\b": "я уверена", r"\bя виноват\b": "я виновата",
        r"\bя должен\b": "я должна", r"\bя мог\b": "я могла",
        r"\bя бы мог\b": "я бы могла", r"\bя был\b": "я была",
        r"\bя сказал\b": "я сказала", r"\bя написал\b": "я написала",
        r"\bя сделал\b": "я сделала", r"\bя исправил\b": "я исправила",
        r"\bя стал\b": "я стала", r"\bя подумал\b": "я подумала",
        r"\bя решил\b": "я решила", r"\bя пытался\b": "я пыталась",
        r"\bя ошибся\b": "я ошиблась",
    }

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"\bя бы([^.!?\n]{0,90})\bне стал\b", r"я бы\1не стала", text, flags=re.IGNORECASE)
    text = re.sub(r"\bя бы([^.!?\n]{0,90})\bпарился\b", r"я бы\1парилась", text, flags=re.IGNORECASE)
    text = re.sub(r"\bя бы([^.!?\n]{0,90})\bсогласился\b", r"я бы\1согласилась", text, flags=re.IGNORECASE)
    text = re.sub(r"\bя бы([^.!?\n]{0,90})\bрешил\b", r"я бы\1решила", text, flags=re.IGNORECASE)
    text = re.sub(r"\bя бы([^.!?\n]{0,90})\bсделал\b", r"я бы\1сделала", text, flags=re.IGNORECASE)

    start_replacements = {
        r"(^|[.!?\n]\s*)понял\b": r"\1поняла",
        r"(^|[.!?\n]\s*)принял\b": r"\1приняла",
        r"(^|[.!?\n]\s*)согласен\b": r"\1согласна",
        r"(^|[.!?\n]\s*)готов\b": r"\1готова",
        r"(^|[.!?\n]\s*)рад\b": r"\1рада",
        r"(^|[.!?\n]\s*)виноват\b": r"\1виновата",
        r"(^|[.!?\n]\s*)не уверен\b": r"\1не уверена",
    }

    for pattern, replacement in start_replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def fix_user_gender_forms(text, user_gender=None):
    user_gender = user_gender or "unknown"
    if user_gender == "female":
        direct = {
            r"\bпонимал\(а\)\b": "понимала", r"\bпонял\(а\)\b": "поняла",
            r"\bхотел\(а\)\b": "хотела", r"\bмог\(ла\)\b": "могла",
            r"\bбыл\(а\)\b": "была", r"\bготов\(а\)\b": "готова",
            r"\bты понял\b": "ты поняла", r"\bты хотел\b": "ты хотела",
            r"\bты мог\b": "ты могла", r"\bты был\b": "ты была",
            r"\bты устал\b": "ты устала", r"\bты нашел\b": "ты нашла",
            r"\bты забыл\b": "ты забыла", r"\bты готов\b": "ты готова",
            r"\bты согласен\b": "ты согласна", r"\bты уверен\b": "ты уверена",
        }
        for pattern, replacement in direct.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        text = re.sub(r"\b([А-Яа-я]+л)\(а\)\b", r"\1а", text)
        return text

    if user_gender == "male":
        text = re.sub(r"\bмог\(ла\)\b", "мог", text, flags=re.IGNORECASE)
        text = re.sub(r"\bбыл\(а\)\b", "был", text, flags=re.IGNORECASE)
        text = re.sub(r"\bготов\(а\)\b", "готов", text, flags=re.IGNORECASE)
        text = re.sub(r"\(а\)", "", text)
        return text

    neutral = {
        r"\bчтобы ты понимал\(а\)\b": "чтобы было понятно",
        r"\bты понимал\(а\)\b": "было понятно",
        r"\bпонимал\(а\)\b": "было понятно",
        r"\bпонял\(а\)\b": "было понятно",
        r"\bты хотел\(а\)\b": "тебе хотелось",
        r"\bхотел\(а\)\b": "хотелось",
        r"\bмог\(ла\)\b": "можно было",
        r"\bбыл\(а\)\b": "было",
        r"\bготов\(а\)\b": "готово",
    }
    for pattern, replacement in neutral.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\b([А-Яа-я]+л)\(а\)\b", r"\1", text)
    text = re.sub(r"\([а-яА-Я]{1,4}\)", "", text)
    return text


SERVICE_PATTERNS = [
    r"\bдай знать\b", r"\bесли\b.{0,60}\bне нравится\b", r"\bесли хочешь\b",
    r"\bесли тебе\b.{0,80}\b(не нравится|не подходит|нужно)\b",
    r"\bмогу\b.{0,60}\b(добавить|убрать|изменить|поменять|подстроиться|обойтись|сделать|поправить)\b",
    r"\bмогу ли я\b", r"\bхочешь, чтобы я\b", r"\bчто добавить\b", r"\bчто убрать\b",
    r"\bкак мне себя вести\b", r"\bкак мне отвечать\b", r"\bкак ей себя вести\b",
    r"\bкак тебе отвечать\b", r"\bтак лучше\??\b", r"\bтеперь лучше\??\b",
    r"\bможешь тыкнуть\b", r"\bможешь сказать\b.{0,40}\b(если|что)\b",
]
BAD_SIMILE_PATTERNS = [r"\bэто как\b.{10,160}", r"\bкак пытаться\b.{5,160}"]


def sentence_is_bad(sentence):
    lower = sentence.lower()
    for pattern in SERVICE_PATTERNS:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            return True
    for pattern in BAD_SIMILE_PATTERNS:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            return True
    return False


def remove_service_sentences(text):
    blocks = re.split(r"(\n+)", text)
    result_blocks = []
    for block in blocks:
        if not block or block.startswith("\n"):
            result_blocks.append(block)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", block)
        kept = [sentence.strip() for sentence in sentences if sentence.strip() and not sentence_is_bad(sentence)]
        result_blocks.append(" ".join(kept))
    result = "".join(result_blocks)
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"[ \t]{2,}", " ", result)
    return result.strip()


def reduce_parenthetical_remarks(text):
    matches = list(re.finditer(r"\(([^()\n]{1,140})\)", text))
    if not matches:
        return text
    kept_count = 0

    def repl(match):
        nonlocal kept_count
        content = match.group(1).strip()
        lower = content.lower()
        if lower in [".. :)", "* .. :) *"]:
            return match.group(0)
        theatrical_triggers = ["дым", "молча", "вздох", "смотр", "хотя", "это тоже", "атмосфер", "диалог", "ремарк", "занавес", "сцена"]
        if kept_count >= 1:
            return ""
        if any(trigger in lower for trigger in theatrical_triggers):
            return ""
        if random.randint(1, 100) <= 65:
            return ""
        kept_count += 1
        return match.group(0)

    text = re.sub(r"\(([^()\n]{1,140})\)", repl, text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\s+,", ",", text)
    return text.strip()


GENERIC_REPEAT_WORDS = {
    "наверное", "впрочем", "действительно", "конечно", "просто", "который", "которая",
    "которое", "которые", "история", "человеческой", "беспомощности", "маленький",
    "маленькая", "маленькое", "выглядит", "потому", "примерно", "разговор",
}


def repeated_reference_words(previous_answer, user_text):
    previous_words = set(re.findall(r"[а-яА-Я]{8,}", (previous_answer or "").lower()))
    user_words = set(re.findall(r"[а-яА-Я]{4,}", (user_text or "").lower()))
    return {word for word in previous_words if word not in user_words and word not in GENERIC_REPEAT_WORDS}


def reduce_repeated_references(text, previous_answer="", user_text=""):
    if not text or not previous_answer:
        return text
    repeated_words = repeated_reference_words(previous_answer, user_text)
    if not repeated_words:
        return text
    sentences = split_to_sentences(text)
    if len(sentences) < 2:
        return text
    kept = []
    removed = 0
    for sentence in sentences:
        lower = sentence.lower()
        has_repeat = any(word in lower for word in repeated_words)
        if has_repeat and removed < 1:
            removed += 1
            continue
        kept.append(sentence)
    if not kept:
        return text
    return " ".join(kept).strip()


def maybe_add_sad_pause(text):
    if not text:
        return text
    stripped = text.strip()
    if stripped.endswith("* .. :) *") or stripped.endswith(".. :)"):
        return text
    lower = stripped.lower()
    sad_words = ["грустно", "печально", "тоскливо", "жалко", "больно", "пусто", "устала", "устал", "одиноч", "мертв", "смерт", "болото", "бессмысленно", "ничего не меняется"]
    short_empty_answer = len(stripped) <= 80 and random.randint(1, 100) <= 10
    sad_context = any(word in lower for word in sad_words) and random.randint(1, 100) <= 18
    if short_empty_answer or sad_context:
        if stripped.endswith("."):
            stripped = stripped[:-1].rstrip()
        stripped += "\n\n.. :)"
    return stripped


def apply_lowercase_mode(text):
    mode = get_setting("lowercase_mode", "off")
    if mode == "on":
        return text.lower()
    if mode == "random" and random.randint(1, 100) <= 35:
        return text.lower()
    return text


def ensure_final_punctuation(text):
    if not text:
        return text
    lines = text.splitlines()
    fixed = []
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            fixed.append(stripped)
            continue
        if stripped.endswith(".. :)"):
            fixed.append(stripped)
            continue
        if is_short_bare_reply_text(stripped):
            fixed.append(stripped.rstrip("."))
            continue
        if stripped[-1] not in ".!?":
            stripped += "."
        fixed.append(stripped)
    return "\n".join(fixed).strip()


def marker_context_allows(user_text, answer_text, triggers):
    corpus = ((user_text or "") + " " + (answer_text or "")).lower().replace("ё", "е")
    corpus = re.sub(r"\b(бтв|имхо|хд|кк)\b", " ", corpus, flags=re.IGNORECASE)
    corpus = re.sub(r"\s+", " ", corpus)
    return any(trigger in corpus for trigger in triggers)


def remove_marker(text, marker):
    pattern = rf"(?i)(^|[\s,.;:!?]){re.escape(marker)}(?=($|[\s,.;:!?]))"
    text = re.sub(pattern, lambda m: m.group(1) if m.group(1).strip() else "", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"^\s*[,.;:!?]\s*", "", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text.strip()


def fix_contextual_speech_markers(text, user_text=""):
    if not text:
        return text

    checks = {
        "бтв": ["к слову", "кстати", "между прочим", "к слову сказать"],
        "имхо": ["по-моему", "по моему", "мое мнение", "считаю", "думаю", "кажется", "я бы"],
        "хд": ["ахах", "хаха", "смешно", "забавно", "лол", "ржу", "угар", ":)"],
        "кк": ["ладно", "хорошо", "ок", "окей", "договорились", "принято", "поняла", "согласна"],
    }

    for marker, triggers in checks.items():
        if re.search(rf"(?i)(^|[\s,.;:!?]){re.escape(marker)}(?=($|[\s,.;:!?]))", text):
            short_agreement = marker == "кк" and len(text.strip()) <= 45
            if not short_agreement and not marker_context_allows(user_text, text, triggers):
                text = remove_marker(text, marker)

    return text.strip()


def remove_unwanted_final_question(text, user_text=""):
    if not text or not text.strip().endswith("?"):
        return text

    sentences = split_to_sentences(text)
    if len(sentences) <= 1:
        return text

    last = sentences[-1].strip()
    last_l = last.lower().replace("ё", "е")

    vague_question_patterns = [
        r"^а ты\??$",
        r"^а у тебя\??$",
        r"^что думаешь\??$",
        r"^как думаешь\??$",
        r"^как считаешь\??$",
        r"^понятно\??$",
        r"^ну как\??$",
        r"^да\??$",
        r"^нет\??$",
        r"^согласна\??$",
        r"^хочешь[^?]{0,80}\??$",
        r"^расскажешь[^?]{0,80}\??$",
        r"^продолжим\??$",
        r"^что у тебя[^?]{0,80}\??$",
    ]

    if len(last) <= 110 and any(re.search(pattern, last_l) for pattern in vague_question_patterns):
        return " ".join(sentences[:-1]).strip()

    service_hooks = ["а ты", "а у тебя", "что думаешь", "как думаешь", "как считаешь", "хочешь", "расскажешь"]
    if len(last) <= 95 and any(hook in last_l for hook in service_hooks):
        return " ".join(sentences[:-1]).strip()

    return text


def clean_answer(text, detailed=False, user_gender=None, user_text=""):
    if not text:
        return ""

    text = text.replace("ё", "е").replace("Ё", "Е")
    text = replace_quotes_with_stars(text)
    text = normalize_punctuation(text)
    text = fix_mixed_english_artifacts(text, detailed=detailed)
    text = fix_contextual_speech_markers(text, user_text=user_text)
    text = fix_bot_self_gender(text)
    text = fix_user_gender_forms(text, user_gender=user_gender)

    text = re.sub(r"(?m)^\s*\*(?!\s*\.\.\s*:\)\s*\*)[^*\n]{1,200}\*\s*\n?", "", text)
    text = re.sub(r"\*(вздыхает|улыбается|смотрит[^*]*|молчит[^*]*|хмыкает[^*]*|сжимает[^*]*|отводит[^*]*|пожимает[^*]*)\*", "", text, flags=re.IGNORECASE)

    bad_phrases = [
        "Теперь лучше?", "Так лучше?", "Вот тебе ядовитый ответ:", "Вот ядовитый ответ:",
        "Ладно, держи краткий чек-лист", "держи краткий чек-лист", "чек-лист для будущего редактирования",
        "Может, я слишком", "Может, ты слишком", "Ты сама меня такой сделала", "Так что теперь терпи",
        "милый пирожочек", "солнышко мое", "солнышко", "зай", "милая", "дорогая", "детка",
        "хочешь, чтобы я стала проще", "если хочешь пофлиртовать", "расскажи мне", "опиши мне",
    ]
    for phrase in bad_phrases:
        text = text.replace(phrase, "")

    text = remove_service_sentences(text)
    text = remove_unwanted_final_question(text, user_text=user_text)
    text = reduce_parenthetical_remarks(text)

    for pattern in [r"\bчурк\w*\b"]:
        text = re.sub(pattern, "[вырезано]", text, flags=re.IGNORECASE)

    replacements = {
        r"\bбля\b": "б*я", r"\bблять\b": "бл*ть", r"\bпиздец\b": "п*здец",
        r"\bпизда\b": "п*зда", r"\bпизду\b": "п*зду", r"\bпиздишь\b": "п*здишь",
        r"\bхуй\b": "х*й", r"\bхуя\b": "х*я", r"\bхуево\b": "х*ево",
        r"\bебать\b": "е*ать", r"\bебаный\b": "е*аный", r"\bебанная\b": "е*анная",
        r"\bзаебала\b": "за*бала", r"\bзаебал\b": "за*бал", r"\bсука\b": "с*ка",
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
        cut_positions = [text.rfind(".", 0, max_len), text.rfind("!", 0, max_len), text.rfind("?", 0, max_len), text.rfind("\n", 0, max_len)]
        cut = max(cut_positions)
        if cut > 180:
            text = text[: cut + 1].strip()
        else:
            text = text[:max_len].strip() + ".."

    text = maybe_add_sad_pause(text)
    text = normalize_punctuation(text)
    text = fix_contextual_speech_markers(text, user_text=user_text)
    text = apply_lowercase_mode(text)
    text = ensure_final_punctuation(text)

    if not text.strip():
        text = "приняла. без протокольной паники."

    return text.strip()
