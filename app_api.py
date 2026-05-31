import hashlib
import random
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from human_engine import install_human_engine, postprocess_dialog_answer

install_human_engine(enable_telegram=False)

from database import init_db
from memory import get_history, get_last_assistant_answer, save_message, prune_user_history, get_recent_messages
from ai import generate_answer


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
BOT_TIMEZONE = "Asia/Krasnoyarsk"

app = FastAPI(title="Soiqweqq Web API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "web"
    client_timezone: str | None = None
    client_offset_minutes: int | None = None
    client_time: str | None = None


def web_ids(session_id: str):
    value = (session_id or "web").strip()
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    user_id = int(digest[:12], 16) % 900000000 + 100000000
    chat_id = -user_id
    return user_id, chat_id


def now_in_zone(zone_name):
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(zone_name))
        except Exception:
            pass
    return datetime.now()


def build_web_time_context(payload: ChatRequest):
    bot_now = now_in_zone(BOT_TIMEZONE)
    bot_offset = bot_now.utcoffset().total_seconds() / 60 if bot_now.utcoffset() else 0

    user_tz = (payload.client_timezone or "").strip() or "unknown"
    user_line = "локальное время собеседника неизвестно"
    diff_line = "разница с собеседником неизвестна"

    if user_tz != "unknown":
        try:
            user_now = now_in_zone(user_tz)
            user_offset = user_now.utcoffset().total_seconds() / 60 if user_now.utcoffset() else 0
            diff_hours = int(round((bot_offset - user_offset) / 60))
            sign = "+" if diff_hours >= 0 else ""
            user_line = f"локальное время собеседника: {user_now.strftime('%Y-%m-%d %H:%M')} ({user_tz})"
            diff_line = f"у Soiqweqq относительно собеседника: {sign}{diff_hours} ч"
        except Exception:
            pass

    return (
        "[контекст веб-чата]\n"
        f"время Soiqweqq: {bot_now.strftime('%Y-%m-%d %H:%M')} ({BOT_TIMEZONE}); {user_line}; {diff_line}. "
        "Используй это только если уместно. Не проговаривай каждый раз.\n\n"
    )



def read_site_track():
    path = BASE_DIR / "site_track.txt"
    if not path.exists():
        path.write_text("Неизвестен | Неизвестно | 0.37\n", encoding="utf-8")
    raw = path.read_text(encoding="utf-8").strip()
    line = next((x.strip() for x in raw.splitlines() if x.strip() and not x.strip().startswith("#")), "")
    parts = [p.strip() for p in line.split("|")]
    artist = parts[0] if len(parts) > 0 and parts[0] else "Неизвестен"
    title = parts[1] if len(parts) > 1 and parts[1] else "Неизвестно"
    try:
        progress = float(parts[2]) if len(parts) > 2 else 0.37
    except Exception:
        progress = 0.37
    progress = max(0.0, min(1.0, progress))
    return {"artist": artist, "title": title, "progress": progress}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "soiqweqq-web", "mode": "alive"}


@app.get("/api/history")
def history(session_id: str = Query("web"), limit: int = Query(40)):
    user_id, chat_id = web_ids(session_id)
    return {"ok": True, "messages": get_recent_messages(user_id, chat_id, limit=limit)}


@app.post("/api/chat")
def chat(payload: ChatRequest):
    user_text = (payload.message or "").strip()
    if not user_text:
        return {"ok": False, "answer": "пустое сообщение. даже для меня это слишком концептуально."}

    user_id, chat_id = web_ids(payload.session_id)

    history = get_history(user_id, chat_id, limit=32)
    previous = get_last_assistant_answer(user_id, chat_id)

    save_message(user_id, chat_id, "user", user_text)

    ai_user_text = build_web_time_context(payload) + "[сообщение пользователя]\n" + user_text
    answer = generate_answer(user_id, chat_id, ai_user_text, history, previous)
    answer = postprocess_dialog_answer(answer, user_text=user_text)

    save_message(user_id, chat_id, "assistant", answer)
    prune_user_history(user_id, chat_id, keep=220)

    return {
        "ok": True,
        "answer": answer,
        "pre_typing_delay_ms": random.randint(1800, 5200),
        "typing_pause_ms": random.randint(700, 1800),
        "typing_speed": random.randint(12, 24),
        "bot_timezone": BOT_TIMEZONE,
        "bot_time": now_in_zone(BOT_TIMEZONE).isoformat(timespec="seconds"),
    }




@app.get("/api/track")
def track():
    return {"ok": True, **read_site_track()}


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/chat")
def chat_page():
    return FileResponse(WEB_DIR / "chat.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
