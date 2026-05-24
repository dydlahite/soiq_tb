from telegram.ext import ApplicationBuilder

from config import TELEGRAM_TOKEN
from database import init_db
from personality import ensure_personality_file
from handlers import register_handlers


def main():
    init_db()
    ensure_personality_file()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    register_handlers(app)

    print("ИИ-бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
