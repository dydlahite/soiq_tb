import re

FORBIDDEN_PHRASES_PATH = "forbidden_phrases.txt"

DEFAULT_FORBIDDEN_PHRASES = """
# Фразы, которые бот не должен писать.
# Одна фраза на строку.
# Можно использовать regex так: re:\\bпример\\b
# После изменения файла сделай systemctl restart bot.

дай знать
если хочешь
если не нравится
могу добавить
могу убрать
могу изменить
могу поменять
как мне себя вести
так лучше?
теперь лучше?
""".strip()


def ensure_forbidden_file():
    try:
        with open(FORBIDDEN_PHRASES_PATH, "x", encoding="utf-8") as file:
            file.write(DEFAULT_FORBIDDEN_PHRASES + "\n")
    except FileExistsError:
        pass


def load_forbidden_phrases():
    ensure_forbidden_file()
    phrases = []

    with open(FORBIDDEN_PHRASES_PATH, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            phrases.append(line)

    return phrases


def clean_forbidden_phrases(text):
    if not text:
        return text

    for phrase in load_forbidden_phrases():
        if phrase.startswith("re:"):
            pattern = phrase[3:].strip()
            if pattern:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            continue

        escaped = re.escape(phrase)
        text = re.sub(escaped, "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
