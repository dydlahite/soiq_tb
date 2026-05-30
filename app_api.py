from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import init_db
from memory import get_history, get_last_assistant_answer, save_message
from ai import generate_answer

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="Soiqweqq Web API", version="1.0")
_lock = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("SOIQ_WEB_CORS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

init_db()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str


def _session_to_int(session_id: str) -> int:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return 700000000 + (int(digest[:10], 16) % 899999999)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "soiqweqq-web"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty message")

    session_id = payload.session_id or "web-anonymous"
    user_id = _session_to_int(session_id)
    chat_id = user_id

    with _lock:
        history = get_history(user_id, chat_id)
        previous_answer = get_last_assistant_answer(user_id, chat_id)
        answer = generate_answer(
            user_id=user_id,
            chat_id=chat_id,
            user_text=text,
            history=history,
            previous_answer=previous_answer,
        )
        save_message(user_id, chat_id, "user", text)
        save_message(user_id, chat_id, "assistant", answer)

    return ChatResponse(answer=answer, session_id=session_id)


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/chat.html")
def chat_page():
    return FileResponse(WEB_DIR / "chat.html")


if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
