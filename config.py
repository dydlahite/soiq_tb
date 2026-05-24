import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

OPENROUTER_DEEPSEEK_MODEL = os.getenv("OPENROUTER_DEEPSEEK_MODEL", "deepseek/deepseek-chat").strip()
OPENROUTER_AUTO_MODEL = os.getenv("OPENROUTER_AUTO_MODEL", "openrouter/auto").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db").strip()
PERSONALITY_PATH = os.getenv("PERSONALITY_PATH", "personality.txt").strip()

ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

DEFAULT_HISTORY_LIMIT = int(os.getenv("DEFAULT_HISTORY_LIMIT", "18"))
DEFAULT_MEDIA_CHANCE = int(os.getenv("DEFAULT_MEDIA_CHANCE", "10"))

if not TELEGRAM_TOKEN:
    raise RuntimeError("Нет TELEGRAM_TOKEN в .env")
