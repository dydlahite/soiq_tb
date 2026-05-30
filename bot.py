from telegram.ext import ApplicationBuilder

from config import TELEGRAM_TOKEN
from database import init_db
from personality import ensure_personality_file
import handlers
from human_engine import install_human_engine


def main():
    init_db()
    ensure_personality_file()
    install_human_engine(enable_telegram=True)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    handlers.register_handlers(app)

    print("ИИ-бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
