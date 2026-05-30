import hashlib
import os
import random
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import init_db
from memory import get_history, get_last_assistant_answer, save_message
from ai import generate_answer


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

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


def web_ids(session_id: str):
    value = (session_id or "web").strip()
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    user_id = int(digest[:12], 16) % 900000000 + 100000000
    chat_id = -user_id
    return user_id, chat_id


@app.get("/api/health")
def health():
    return {"ok": True, "service": "soiqweqq-web", "mode": "alive"}


@app.post("/api/chat")
def chat(payload: ChatRequest):
    user_text = (payload.message or "").strip()
    if not user_text:
        return {"ok": False, "answer": "пустое сообщение. даже для меня это слишком концептуально."}

    user_id, chat_id = web_ids(payload.session_id)

    history = get_history(user_id, chat_id)
    previous = get_last_assistant_answer(user_id, chat_id)

    save_message(user_id, chat_id, "user", user_text)
    answer = generate_answer(user_id, chat_id, user_text, history, previous)
    save_message(user_id, chat_id, "assistant", answer)

    return {
        "ok": True,
        "answer": answer,
        "delay_ms": random.randint(900, 2400),
        "typing_speed": random.randint(12, 24),
    }


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/chat")
def chat_page():
    return FileResponse(WEB_DIR / "chat.html")


app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
