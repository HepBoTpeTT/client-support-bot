import logging
import os
import threading
import time
import traceback
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy import func, desc, text, and_, or_
from sqlalchemy.orm import Session
from urllib.parse import quote

from config import settings
from crawler import crawl_site, search_chunks
from database import get_db, init_db, SessionLocal, engine
from models import (
    Settings as SettingsModel, Page, Chunk, Dialog,
    CrawlSession, Achievement, DailyTask,
    # OperatorSession, OperatorMessage,
)
from qdrant_store import search_similar, clear_collection

from pathlib import Path
from fastapi.staticfiles import StaticFiles


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Отключаем избыточные логи httpx и hpack
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)



from fastembed import TextEmbedding
for m in TextEmbedding.list_supported_models():
    logger.info(m["model"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrate: add chat_bg_color BEFORE init_db reads the table
    try:
        with engine.connect() as _conn:
            _conn.execute(text(
                "ALTER TABLE settings ADD COLUMN chat_bg_color VARCHAR(32) DEFAULT '#f8f9fb'"
            ))
            _conn.commit()
            logger.info("Migrated: added chat_bg_color column")
    except Exception:
        pass  # Column already exists or table doesn't exist yet

    try:
        with engine.connect() as _conn:
            _conn.execute(text(
                "ALTER TABLE settings ADD COLUMN text_color VARCHAR(32) DEFAULT '#222222'"
            ))
            _conn.commit()
    except Exception:
        pass
    init_db()
    logger.info("Database initialized")
    # Автоочистка: если бэк был прерван на середине парсинга —
    # сессии висят в running. Сбрасываем их при каждом запуске.
    try:
        _db = SessionLocal()
        stale = _db.query(CrawlSession).filter(CrawlSession.status == "running").all()
        for s in stale:
            s.status = "error"
            s.error_message = "Бэкенд был перезапущен во время парсинга"
            s.finished_at = datetime.now(timezone.utc)
        if stale:
            _db.commit()
            logger.warning(f"Сброшено {len(stale)} зависших сессий парсинга")
        _db.close()
    except Exception as e:
        logger.error(f"Ошибка при очистке сессий: {e}")

    yield


app = FastAPI(title="Site Assistant API", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
WIDGET_STATIC_DIR = BASE_DIR / "widget-static"

app.mount(
    "/widget-static",
    StaticFiles(directory=WIDGET_STATIC_DIR),
    name="widget-static",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────
# Сonstants
# ──────────────────────────────────────────────────────────

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_OPERATOR = "operator"
ROLE_SYSTEM = "system"

EVENT_MESSAGE = "message"
EVENT_HANDOFF_REQUESTED = "handoff_requested"
EVENT_HANDOFF_CLOSED = "handoff_closed"
EVENT_HANDOFF_REOPENED = "handoff_reopened"

# ──────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────
class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

class SettingsUpdate(CamelModel):
    openai_key: str | None = None
    bot_name: str | None = None
    welcome_message: str | None = None
    accent_color: str | None = None
    language: str | None = None
    system_prompt: str | None = None
    target_url: str | None = None
    model: str | None = None
    crawler_settings: str | None = None
    chat_bg_color: str | None = None
    user_bubble_bg: str | None = None
    user_text_color: str | None = None
    bot_bubble_bg: str | None = None
    bot_text_color: str | None = None


class CrawlStartRequest(BaseModel):
    url: str


class ChatRequest(BaseModel):
    message: str
    session_id: str


# ──────────────────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────────────────

def mask_key(key: str) -> str:
    if not key:
        return ""
    return "••••••••" + key[-4:]


def settings_to_dict(s: SettingsModel, mask: bool = True) -> dict:
    return {
        "id": s.id,
        "openaiKey": mask_key(s.openai_key) if mask else s.openai_key,
        "botName": s.bot_name,
        "welcomeMessage": s.welcome_message,
        "accentColor": s.accent_color,
        "language": s.language,
        "systemPrompt": s.system_prompt,
        "targetUrl": s.target_url,
        "model": s.model,
        "crawlerSettings": s.crawler_settings,
        "chatBgColor": getattr(s, "chat_bg_color", "#f8f9fb") or "#f8f9fb",
        "userBubbleBg": getattr(s, "user_bubble_bg", "#01696f") or "#01696f",
        "userTextColor": getattr(s, "user_text_color", "#ffffff") or "#ffffff",
        "botBubbleBg": getattr(s, "bot_bubble_bg", "#ffffff") or "#ffffff",
        "botTextColor": getattr(s, "bot_text_color", "#222222") or "#222222",
    }

class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"

def build_system_prompt(s: SettingsModel, context: str) -> str:
    lang_map = {
        "ru": "русском",
        "en": "английском",
        "uk": "украинском",
    }

    template = (s.system_prompt or "").strip()
    if not template:
        template = (
            "Ты — {bot_name}, вежливый и компетентный AI-помощник сайта.\n"
            "Отвечай только по теме сайта и его услуг/товаров.\n"
            "Если вопрос не по теме — вежливо перенаправь.\n"
            "Отвечай на {language} языке.\n"
            "Используй следующий контекст из базы знаний сайта:\n\n"
            "{context}"
        )

    values = SafeDict(
        bot_name=s.bot_name or "Помощник",
        language=lang_map.get(s.language, s.language or "русском"),
        context=context or "База знаний пуста. Ответь на основе общих знаний.",
        welcome_message=s.welcome_message or "",
        model=s.model or "gpt-4o",
        target_url=s.target_url or "",
    )

    return template.format_map(values).strip()


@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    if not s:
        raise HTTPException(status_code=500, detail="Settings not found")
    return settings_to_dict(s)


@app.patch("/api/settings")
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    if not s:
        raise HTTPException(status_code=500, detail="Settings not found")

    update_data = data.model_dump(exclude_none=True)

    if "openai_key" in update_data and update_data["openai_key"].startswith("••••"):
        update_data.pop("openai_key")

    for field, value in update_data.items():
        setattr(s, field, value)

    db.commit()
    db.refresh(s)
    return settings_to_dict(s)


# ──────────────────────────────────────────────────────────
# Crawl
# ──────────────────────────────────────────────────────────

@app.post("/api/crawl/start")
async def start_crawl(
    req: CrawlStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL обязателен")

    session = CrawlSession(
        target_url=req.url,
        status="running",
        pages_found=0,
        pages_done=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session_id = session.id

    # Save URL to settings
    s = db.query(SettingsModel).first()
    if s:
        s.target_url = req.url
        db.commit()

    def run_crawl_sync():
        crawl_db = SessionLocal()
        try:
            crawl_site(session_id, req.url, crawl_db)
        except Exception as e:
            logger.error(f"Crawl error: {e}")
            logger.error(traceback.format_exc())
            sess = crawl_db.get(CrawlSession, session_id)
            if sess:
                sess.status = "error"
                sess.error_message = str(e)
                sess.finished_at = datetime.now(timezone.utc)
                crawl_db.commit()
        finally:
            crawl_db.close()

    t = threading.Thread(target=run_crawl_sync, daemon=True)
    t.start()
    return {"sessionId": session_id, "status": "running"}


@app.get("/api/crawl/status")
def get_crawl_status(db: Session = Depends(get_db)):
    session = db.query(CrawlSession).order_by(desc(CrawlSession.id)).first()
    if not session:
        return {"status": "idle"}
    return {
        "id": session.id,
        "targetUrl": session.target_url,
        "status": session.status,
        "pagesFound": session.pages_found,
        "pagesDone": session.pages_done,
        "startedAt": session.started_at.isoformat() if session.started_at else None,
        "finishedAt": session.finished_at.isoformat() if session.finished_at else None,
        "errorMessage": session.error_message,
    }


@app.get("/api/crawl/sessions")
def get_crawl_sessions(db: Session = Depends(get_db)):
    sessions = db.query(CrawlSession).order_by(desc(CrawlSession.id)).all()
    return [
        {
            "id": s.id,
            "targetUrl": s.target_url,
            "status": s.status,
            "pagesFound": s.pages_found,
            "pagesDone": s.pages_done,
            "startedAt": s.started_at.isoformat() if s.started_at else None,
            "finishedAt": s.finished_at.isoformat() if s.finished_at else None,
            "errorMessage": s.error_message,
        }
        for s in sessions
    ]


@app.delete("/api/crawl/sessions")
def delete_crawl_history(db: Session = Depends(get_db)):
    """Delete all crawl sessions history (keeps pages/chunks intact)."""
    db.query(CrawlSession).delete()
    db.commit()
    return {"ok": True}


@app.delete("/api/dialogs")
def delete_all_dialogs(db: Session = Depends(get_db)):
    """Delete all chat sessions and messages."""
    db.query(Dialog).delete()
    db.commit()
    return {"ok": True}


@app.delete("/api/dialogs/{session_id}")
def delete_dialog_session(session_id: str, db: Session = Depends(get_db)):
    """Delete one chat session."""
    db.query(Dialog).filter(Dialog.session_id == session_id).delete()
    db.commit()
    return {"ok": True}


# ──────────────────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────────────────

@app.get("/api/pages")
def get_pages(db: Session = Depends(get_db)):
    rows = db.execute(text(
        """
        SELECT id, url, title, status, crawled_at, CHAR_LENGTH(content) AS content_len FROM pages ORDER BY id
        """
    )).fetchall()

    return [
        {
            "id": r[0],
            "url": r[1],
            "title": r[2],
            "status": r[3],
            "crawledAt": r[4].isoformat() if r[4] else None,
            "contentLen": r[5],
        }
        for r in rows
    ]

@app.get("/api/pages/{page_id}/content")
def get_page_content(page_id: int, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"content": page.content}

@app.delete("/api/pages/{page_id}")
def delete_page(page_id: int, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    db.delete(page)
    db.commit()
    return {"ok": True}


@app.delete("/api/pages")
def clear_pages(db: Session = Depends(get_db)):
    err = False
    try:
        db.query(Chunk).delete()
        db.query(Page).delete()
        db.commit()
        clear_collection()
    except:
        err = True
    return {"ok": not err}


# ──────────────────────────────────────────────────────────
# Chat (RAG + GPT-4o)
# ──────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    if not req.message or not req.session_id:
        raise HTTPException(status_code=400, detail="message и session_id обязательны")

    s = db.query(SettingsModel).first()
    if not s or not s.openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API ключ не настроен. Обратитесь к администратору.")

    history = (
        db.query(Dialog)
        .filter(
            Dialog.session_id == req.session_id,
            Dialog.event_type == EVENT_MESSAGE,
            Dialog.role.in_([ROLE_USER, ROLE_ASSISTANT]),
        )
        .order_by(Dialog.created_at.asc(), Dialog.id.asc())
        .limit(8)
        .all()
    )

    db.add(Dialog(
        session_id=req.session_id,
        role=ROLE_USER,
        event_type=EVENT_MESSAGE,
        content=req.message,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    relevant_chunks = []
    retrieval_backend = "none"

    try:
        relevant_chunks = search_similar(req.message, limit=5)
        retrieval_backend = "qdrant"
    except Exception as e:
        logger.warning(f"Qdrant search failed, fallback to MySQL: {e}")
        try:
            mysql_chunks = search_chunks(db, req.message, limit=5)
            relevant_chunks = [
                {
                    "chunk_text": c.chunk_text,
                    "page_url": c.page_url,
                    "page_title": c.page_title,
                    "score": None,
                }
                for c in mysql_chunks
            ]
            retrieval_backend = "mysql"
        except Exception as e2:
            logger.error(f"MySQL fallback search failed: {e2}")
            relevant_chunks = []
            retrieval_backend = "none"

    if relevant_chunks:
        context = "\n\n---\n\n".join(
            f"[Источник: {c['page_title']} ({c['page_url']})]\n{c['chunk_text']}"
            for c in relevant_chunks
        )
    else:
        context = "База знаний пуста. Ответь на основе общих знаний."

    logging.info("Контекст, направляемый в OpenAI API: \n%s", context)

    system_prompt = build_system_prompt(s, context)
    _proxy = settings.openai_proxy or settings.http_proxy or None
    if _proxy:
        try:
            _http_client = httpx.AsyncClient(proxy=_proxy)
        except TypeError:
            _http_client = httpx.AsyncClient(proxies={"http://": _proxy, "https://": _proxy})
    else:
        _http_client = None

    logger.info(f"OpenAI proxy: {_proxy!r}")
    client = AsyncOpenAI(
        api_key=s.openai_key,
        http_client=_http_client
    )

    messages = [{"role": "system", "content": system_prompt}]
    for d in history:
        messages.append({"role": d.role, "content": d.content})
    messages.append({"role": "user", "content": req.message})

    logging.info("Сообщение, отправляемое боту:\n%s", messages)

    try:
        completion = await client.chat.completions.create(
            model=s.model or "gpt-4o",
            messages=messages,
            max_tokens=800,
            temperature=0.5,
        )
        reply = completion.choices[0].message.content or "Извините, не могу ответить прямо сейчас."
    except Exception as e:
        logger.error(f"OpenAI error: {traceback.format_exc()}")
        reply = "Извините, сейчас временно не удаётся получить ответ. Попробуйте ещё раз чуть позже."
        raise HTTPException(status_code=500, detail=f"OpenAI ошибка: {str(e)}")

    finally:
        db.add(Dialog(
            session_id=req.session_id,
            role="assistant",
            content=reply,
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()

    return {
        "reply": reply,
        "sourcesUsed": len(relevant_chunks),
        "retrievalBackend": retrieval_backend,
    }

# ──────────────────────────────────────────────────────────
# Dialogs
# ──────────────────────────────────────────────────────────

def dialog_preview_text(d: Dialog | None) -> str:
    if not d:
        return ""

    if d.event_type == "handoff_requested":
        return "Запрошен оператор"

    if d.event_type == "handoff_closed":
        return "Обращение закрыто"

    if d.event_type == "handoff_reopened":
        return "Обращение открыто повторно"

    if d.event_type == "message":
        if d.role == "operator":
            return f"Оператор: {(d.content or '').strip()[:100]}"
        if d.role == "assistant":
            return f"Бот: {(d.content or '').strip()[:100]}"
        if d.role == "user":
            return (d.content or "").strip()[:100]
        return (d.content or "").strip()[:100]

    return "Системное событие"

@app.get("/api/dialogs")
def get_dialog_sessions(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Dialog.session_id,
            func.count(Dialog.id).label("count"),
            func.max(Dialog.created_at).label("last_at"),
        )
        .group_by(Dialog.session_id)
        .order_by(desc("last_at"))
        .all()
    )

    result = []
    for row in rows:
        last_user_msg = (
            db.query(Dialog)
            .filter(
                Dialog.session_id == row.session_id,
                Dialog.role == ROLE_USER,
            )
            .order_by(desc(Dialog.created_at), desc(Dialog.id))
            .first()
        )

        result.append({
            "sessionId": row.session_id,
            "count": row.count,
            "createdAt": last_user_msg.created_at.isoformat() if last_user_msg and last_user_msg.created_at else None,
            "lastMessage": dialog_preview_text(last_user_msg),
        })

    return result

@app.get("/api/dialogs/{session_id}")
def get_session_dialogs(session_id: str, db: Session = Depends(get_db)):
    dialogs = (
        db.query(Dialog)
        .filter(Dialog.session_id == session_id)
        .order_by(Dialog.created_at, Dialog.id)
        .all()
    )
    return [
        {
            "id": d.id,
            "sessionId": d.session_id,
            "role": d.role,
            "eventType": d.event_type,
            "content": d.content,
            "createdAt": d.created_at.isoformat() if d.created_at else None,
        }
        for d in dialogs
    ]

# ──────────────────────────────────────────────────────────
# Operator handoff
# ──────────────────────────────────────────────────────────

class OperatorSendRequest(BaseModel):
    session_id: str
    message: str

class UserOperatorMessageRequest(BaseModel):
    session_id: str
    message: str
    last_id: Optional[int] = 0


@app.post("/api/operator/request")
def request_operator(req: ChatRequest, db: Session = Depends(get_db)):
    """User requests to be connected to a human operator."""

    last_event = (
        db.query(Dialog)
        .filter(
            Dialog.session_id == req.session_id,
            Dialog.event_type.in_([
                EVENT_HANDOFF_REQUESTED,
                EVENT_HANDOFF_CLOSED,
                EVENT_HANDOFF_REOPENED,
            ]),
        )
        .order_by(desc(Dialog.created_at), desc(Dialog.id))
        .first()
    )

    next_event = EVENT_HANDOFF_REOPENED if last_event and last_event.event_type == EVENT_HANDOFF_CLOSED else EVENT_HANDOFF_REQUESTED

    db.add(Dialog(
        session_id=req.session_id,
        role=ROLE_SYSTEM,
        event_type=next_event,
        content=None,
        created_at=datetime.now(timezone.utc),
    ))

    if req.message and req.message.strip():
        db.add(Dialog(
            session_id=req.session_id,
            role=ROLE_USER,
            event_type=EVENT_MESSAGE,
            content=req.message.strip(),
            created_at=datetime.now(timezone.utc),
        ))

    db.commit()
    return {"ok": True, "status": "pending"}

@app.post("/api/operator/user-message")
def user_operator_message(req: UserOperatorMessageRequest, db: Session = Depends(get_db)):
    """User sends a message while in operator mode."""
    status = get_operator_status(req.session_id, db)

    if status in ("none", "closed"):
        raise HTTPException(status_code=400, detail="Нет активной сессии с оператором")

    db.add(Dialog(
        session_id=req.session_id,
        role=ROLE_USER,
        event_type=EVENT_MESSAGE,
        content=req.message.strip(),
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    return {"ok": True}

@app.get("/api/operator/sessions")
def get_operator_sessions(db: Session = Depends(get_db)):
    """Admin: list all operator sessions with computed status and last message."""
    now_utc = datetime.now(timezone.utc)
    start_of_today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_yesterday = start_of_today_utc - timedelta(days=1)

    session_rows = (
        db.query(
            Dialog.session_id,
            func.min(Dialog.created_at).label("created_at"),
            func.max(Dialog.created_at).label("updated_at"),
        )
        .filter(
            Dialog.session_id.in_(
                db.query(Dialog.session_id).filter(
                    Dialog.event_type.in_([
                        EVENT_HANDOFF_REQUESTED,
                        EVENT_HANDOFF_REOPENED,
                        EVENT_HANDOFF_CLOSED,
                    ])
                )
            ),
            Dialog.created_at >= start_of_yesterday,
        )
        .group_by(Dialog.session_id)
        .order_by(desc("updated_at"))
        .all()
    )

    result = []
    for row in session_rows:
        status = get_operator_status(row.session_id, db)
        if status == "none":
            continue

        last_msg = get_last_dialog_entry(row.session_id, db)

        user_message_count = db.query(Dialog).filter(
            Dialog.session_id == row.session_id,
            Dialog.role == ROLE_USER,
            Dialog.event_type == EVENT_MESSAGE,
        ).count()

        result.append({
            "id": row.session_id,
            "sessionId": row.session_id,
            "status": status,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
            "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
            "lastMessage": get_operator_preview_text(last_msg),
            "lastMessageRole": last_msg.role if last_msg else "",
            "userMessageCount": user_message_count,
        })

    return result

@app.get("/api/operator/messages/{session_id}")
def get_operator_messages(session_id: str, db: Session = Depends(get_db)):
    """Get full operator timeline for a session."""
    status = get_operator_status(session_id, db)
    if status == "none":
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    msgs = (
        db.query(Dialog)
        .filter(Dialog.session_id == session_id)
        .order_by(Dialog.created_at.asc(), Dialog.id.asc())
        .all()
    )

    return [
        {
            "id": m.id,
            "sessionId": m.session_id,
            "role": m.role,
            "eventType": m.event_type,
            "content": m.content,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]

@app.get("/api/operator/poll/{session_id}")
def poll_operator_messages(session_id: str, last_id: int = 0, db: Session = Depends(get_db)):
    """Widget polling: get new operator messages since last_id."""
    status = get_operator_status(session_id, db)

    if status == "none":
        return {"status": "none", "messages": []}

    msgs = (
        db.query(Dialog)
        .filter(
            Dialog.session_id == session_id,
            Dialog.id > last_id,
            Dialog.role == ROLE_OPERATOR,
            Dialog.event_type == EVENT_MESSAGE,
        )
        .order_by(Dialog.created_at.asc(), Dialog.id.asc())
        .all()
    )

    return {
        "status": status,
        "messages": [
            {
                "id": m.id,
                "content": m.content,
                "createdAt": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }

@app.post("/api/operator/send")
def operator_send(req: OperatorSendRequest, db: Session = Depends(get_db)):
    """Admin/operator sends message to user."""

    if not req.session_id or not req.message.strip():
        raise HTTPException(status_code=400, detail="session_id и message обязательны")

    has_handoff = db.query(Dialog).filter(
        Dialog.session_id == req.session_id,
        Dialog.event_type.in_([
            EVENT_HANDOFF_REQUESTED,
            EVENT_HANDOFF_REOPENED,
            EVENT_HANDOFF_CLOSED,
        ]),
    ).count() > 0

    if not has_handoff:
        raise HTTPException(status_code=404, detail="Сессия оператора не найдена")

    last_event = (
        db.query(Dialog)
        .filter(
            Dialog.session_id == req.session_id,
            Dialog.event_type.in_([
                EVENT_HANDOFF_REQUESTED,
                EVENT_HANDOFF_REOPENED,
                EVENT_HANDOFF_CLOSED,
            ]),
        )
        .order_by(desc(Dialog.created_at), desc(Dialog.id))
        .first()
    )

    if last_event and last_event.event_type == EVENT_HANDOFF_CLOSED:
        db.add(Dialog(
            session_id=req.session_id,
            role=ROLE_SYSTEM,
            event_type=EVENT_HANDOFF_REOPENED,
            content=None,
            created_at=datetime.now(timezone.utc),
        ))

    db.add(Dialog(
        session_id=req.session_id,
        role=ROLE_OPERATOR,
        event_type=EVENT_MESSAGE,
        content=req.message.strip(),
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    return {"ok": True}

@app.patch("/api/operator/sessions/{session_id}")
def update_operator_session(session_id: str, db: Session = Depends(get_db)):
    """Close/reopen an operator session via Dialog events."""
    status = get_operator_status(session_id, db)

    if status == "none":
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    if status == "closed":
        next_event = EVENT_HANDOFF_REOPENED
        next_status = "pending"
    else:
        next_event = EVENT_HANDOFF_CLOSED
        next_status = "closed"

    db.add(Dialog(
        session_id=session_id,
        role=ROLE_SYSTEM,
        event_type=next_event,
        content=None,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    return {"ok": True, "status": next_status}

# ──────────────────────────────────────────────────────────
# Operator helpers
# ──────────────────────────────────────────────────────────


def get_operator_status(session_id: str, db: Session) -> str:
    last_start_event = (
        db.query(Dialog)
        .filter(
            Dialog.session_id == session_id,
            Dialog.event_type.in_([EVENT_HANDOFF_REQUESTED, EVENT_HANDOFF_REOPENED]),
        )
        .order_by(desc(Dialog.created_at), desc(Dialog.id))
        .first()
    )

    if not last_start_event:
        return "none"

    has_close = db.query(Dialog).filter(
        Dialog.session_id == session_id,
        Dialog.event_type == EVENT_HANDOFF_CLOSED,
        happened_after(last_start_event),
    ).count() > 0

    if has_close:
        return "closed"

    has_operator_reply = db.query(Dialog).filter(
        Dialog.session_id == session_id,
        Dialog.role == ROLE_OPERATOR,
        Dialog.event_type == EVENT_MESSAGE,
        happened_after(last_start_event),
    ).count() > 0

    return "active" if has_operator_reply else "pending"

def get_last_operator_message(session_id: str, db: Session) -> Dialog | None:
    return (
        db.query(Dialog)
        .filter(Dialog.session_id == session_id)
        .order_by(desc(Dialog.created_at), desc(Dialog.id))
        .first()
    )

def happened_after(row: Dialog):
    return or_(
        Dialog.created_at > row.created_at,
        and_(Dialog.created_at == row.created_at, Dialog.id > row.id),
    )

def get_last_handoff_start(session_id: str, db: Session) -> Dialog | None:
    return (
        db.query(Dialog)
        .filter(
            Dialog.session_id == session_id,
            Dialog.event_type.in_([EVENT_HANDOFF_REQUESTED, EVENT_HANDOFF_REOPENED]),
        )
        .order_by(desc(Dialog.created_at), desc(Dialog.id))
        .first()
    )

def get_operator_status(session_id: str, db: Session) -> str:
    last_start = get_last_handoff_start(session_id, db)
    if not last_start:
        return "none"

    has_close = db.query(Dialog).filter(
        Dialog.session_id == session_id,
        Dialog.event_type == EVENT_HANDOFF_CLOSED,
        happened_after(last_start),
    ).count() > 0

    if has_close:
        return "closed"

    has_operator_reply = db.query(Dialog).filter(
        Dialog.session_id == session_id,
        Dialog.role == ROLE_OPERATOR,
        Dialog.event_type == EVENT_MESSAGE,
        happened_after(last_start),
    ).count() > 0

    return "active" if has_operator_reply else "pending"

def get_last_dialog_entry(session_id: str, db: Session) -> Dialog | None:
    return (
        db.query(Dialog)
        .filter(
            Dialog.session_id == session_id,
            Dialog.role == ROLE_USER,
            )
        .order_by(desc(Dialog.created_at), desc(Dialog.id))
        .first()
    )

def get_operator_preview_text(d: Dialog | None) -> str:
    if not d:
        return ""

    if d.event_type == EVENT_HANDOFF_REQUESTED:
        return "Запрошен оператор"
    if d.event_type == EVENT_HANDOFF_REOPENED:
        return "Обращение открыто повторно"
    if d.event_type == EVENT_HANDOFF_CLOSED:
        return "Обращение закрыто"

    text = (d.content or "").strip()
    if d.role == ROLE_OPERATOR:
        return f"Оператор: {text[:120]}"
    if d.role == ROLE_ASSISTANT:
        return f"Бот: {text[:120]}"
    return text[:120]


# ──────────────────────────────────────────────────────────
# Gamification helpers
# ──────────────────────────────────────────────────────────

# Full catalogue of achievements with thresholds
ACHIEVEMENT_CATALOGUE = [
    # Key, emoji, title, description, category
    ("first_crawl",        "🚀", "Первый парсинг",          "Запустите парсинг сайта впервые",          "crawler"),
    ("crawl_5",            "🔄", "5 запусков",             "Запустите парсинг 5 раз",                    "crawler"),
    ("crawl_20",           "🌠", "20 запусков",            "Запустите парсинг 20 раз",                   "crawler"),
    ("pages_10",           "📚", "10 страниц",             "Парсинг 10+ страниц за раз",          "crawler"),
    ("pages_50",           "📖", "50 страниц",             "Парсинг 50+ страниц за раз",          "crawler"),
    ("pages_200",          "🏆", "200 страниц",            "Полный парсинг 200 страниц",             "crawler"),
    ("first_dialog",       "💬", "Первый диалог",          "Первый пользователь написал боту",     "dialogs"),
    ("dialogs_10",         "🗨️", "10 диалогов",            "Бот ответил на 10 сессий",                "dialogs"),
    ("dialogs_50",         "📞", "50 диалогов",            "Бот ответил на 50 сессий",                "dialogs"),
    ("dialogs_200",        "🏅", "200 диалогов",           "Бот ответил на 200 сессий",               "dialogs"),
    ("messages_100",       "📨", "100 сообщений",          "Бот получил 100 сообщений от пользователей",  "dialogs"),
    ("messages_1000",      "📡", "1000 сообщений",         "Бот получил 1000 сообщений",                 "dialogs"),
    ("first_operator",     "🧑‍💻", "Первое обращение",       "Первый запрос оператору",               "operator"),
    ("operator_10",        "🎧", "10 обращений",           "Отвечено 10 запросов оператору",        "operator"),
    ("operator_50",        "🏄", "50 обращений",           "Отвечено 50 запросов",                   "operator"),
    ("settings_configured","⚙️",  "Настройка выполнена",    "Заполнены все настройки бота",           "settings"),
    ("daily_7",            "🗓️", "7 дней подряд",         "Выполняйте задачи 7 дней подряд",     "daily"),
    ("daily_30",           "📅", "30 дней подряд",        "Выполняйте задачи 30 дней подряд",    "daily"),
]
ACHIEVEMENT_MAP = {a[0]: {"emoji": a[1], "title": a[2], "description": a[3], "category": a[4]} for a in ACHIEVEMENT_CATALOGUE}

# Task definitions (static, frontend renders icons)
DAILY_TASK_DEFS = [
    {"key": "check_dialogs",   "title": "Просмотреть историю диалогов",   "icon": "MessageSquare"},
    {"key": "check_crm",       "title": "Проверить заявки в CRM",          "icon": "ShoppingCart", "no_action": True},
]


def try_unlock(db: Session, key: str) -> bool:
    """Unlock achievement if not already unlocked. Returns True if newly unlocked."""
    existing = db.query(Achievement).filter(Achievement.key == key).first()
    if existing:
        return False
    db.add(Achievement(key=key, unlocked_at=datetime.now(timezone.utc), is_new=True))
    db.commit()
    return True


def count_answered_operator_sessions(db: Session) -> int:
    return db.query(Dialog.session_id).filter(
        Dialog.role == ROLE_OPERATOR,
        Dialog.event_type == EVENT_MESSAGE,
    ).distinct().count()


def check_achievements(db: Session) -> list[str]:
    """Re-evaluate all threshold achievements. Returns list of newly unlocked keys."""
    newly = []

    crawl_count = db.query(CrawlSession).filter(CrawlSession.status == "done").count()
    last_crawl = db.query(CrawlSession).filter(CrawlSession.status == "done").order_by(desc(CrawlSession.id)).first()
    max_pages = last_crawl.pages_done if last_crawl else 0

    dialog_sessions = db.query(Dialog.session_id).distinct().count()
    total_messages = db.query(Dialog).filter(
        Dialog.role == ROLE_USER,
        Dialog.event_type == EVENT_MESSAGE,
    ).count()

    operator_requested_sessions = db.query(Dialog.session_id).filter(
        Dialog.event_type.in_([
            EVENT_HANDOFF_REQUESTED,
            EVENT_HANDOFF_REOPENED,
        ])
    ).distinct().count()

    operator_answered_sessions = db.query(Dialog.session_id).filter(
        Dialog.role == ROLE_OPERATOR,
        Dialog.event_type == EVENT_MESSAGE,
    ).distinct().count()

    s = db.query(SettingsModel).first()

    checks = [
        ("first_crawl", crawl_count >= 1),
        ("crawl_5", crawl_count >= 5),
        ("crawl_20", crawl_count >= 20),
        ("pages_10", max_pages >= 10),
        ("pages_50", max_pages >= 50),
        ("pages_200", max_pages >= 200),

        ("first_dialog", dialog_sessions >= 1),
        ("dialogs_10", dialog_sessions >= 10),
        ("dialogs_50", dialog_sessions >= 50),
        ("dialogs_200", dialog_sessions >= 200),
        ("messages_100", total_messages >= 100),
        ("messages_1000", total_messages >= 1000),

        ("first_operator", operator_requested_sessions >= 1),
        ("operator_10", operator_answered_sessions >= 10),
        ("operator_50", operator_answered_sessions >= 50),

        ("settings_configured", bool(s and s.openai_key and s.bot_name and s.target_url)),
    ]

    for key, condition in checks:
        if condition and try_unlock(db, key):
            newly.append(key)

    return newly

class CompleteTaskRequest(BaseModel):
    task_key: str


@app.get("/api/gamification")
def get_gamification(db: Session = Depends(get_db)):
    """Return achievements and today's daily tasks status."""
    # Trigger achievement check on every load
    check_achievements(db)

    unlocked = db.query(Achievement).order_by(desc(Achievement.unlocked_at)).all()
    unlocked_keys = {a.key for a in unlocked}

    # Build full catalogue with unlocked flag
    catalogue = []
    for key, meta in ACHIEVEMENT_MAP.items():
        a = next((x for x in unlocked if x.key == key), None)
        catalogue.append({
            "key": key,
            "emoji": meta["emoji"],
            "title": meta["title"],
            "description": meta["description"],
            "category": meta["category"],
            "unlocked": key in unlocked_keys,
            "unlockedAt": a.unlocked_at.isoformat() if a else None,
            "isNew": bool(a.is_new) if a else False,
        })

    # Today's tasks
    today = datetime.now(timezone.utc).date().isoformat()
    completed_today = {
        r.task_key
        for r in db.query(DailyTask).filter(DailyTask.completed_date == today).all()
    }
    tasks = [
        {
            **t,
            "completed": t["key"] in completed_today,
        }
        for t in DAILY_TASK_DEFS
    ]

    new_count = sum(1 for a in unlocked if a.is_new)

    # Count pending operator requests (new appeals)
    operator_session_ids = [
        row[0]
        for row in db.query(Dialog.session_id)
        .filter(
            Dialog.event_type.in_([
                EVENT_HANDOFF_REQUESTED,
                EVENT_HANDOFF_REOPENED,
                EVENT_HANDOFF_CLOSED,
            ])
        )
        .distinct()
        .all()
    ]

    pending_operators = sum(
        1 for session_id in operator_session_ids
        if get_operator_status(session_id, db) == "pending"
    )

    return {
        "achievements": catalogue,
        "tasks": tasks,
        "stats": {
            "total": len(catalogue),
            "unlocked": len(unlocked_keys),
            "newCount": new_count,
            "pendingOperators": pending_operators,
        },
    }


@app.post("/api/gamification/complete-task")
def complete_daily_task(req: CompleteTaskRequest, db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date().isoformat()
    exists = db.query(DailyTask).filter(
        DailyTask.task_key == req.task_key,
        DailyTask.completed_date == today,
    ).first()
    if not exists:
        db.add(DailyTask(task_key=req.task_key, completed_date=today, completed_at=datetime.now(timezone.utc)))
        db.commit()

        # Check streak achievements
        # Count distinct dates with ALL tasks completed
        all_keys = {t["key"] for t in DAILY_TASK_DEFS}
        # Get all completed dates
        rows = db.execute(
            text("""
                SELECT completed_date, COUNT(DISTINCT task_key) as cnt
                FROM daily_tasks
                GROUP BY completed_date
                HAVING cnt >= :total
                ORDER BY completed_date DESC
            """),
            {"total": len(all_keys)}
        ).fetchall()
        # Compute streak
        streak = 0
        check_date = date.today()
        date_set = {r[0] for r in rows}
        while check_date.strftime("%Y-%m-%d") in date_set:
            streak += 1
            check_date -= timedelta(days=1)

        if streak >= 7:
            try_unlock(db, "daily_7")
        if streak >= 30:
            try_unlock(db, "daily_30")

    check_achievements(db)
    return {"ok": True}


@app.post("/api/gamification/mark-seen")
def mark_achievements_seen(db: Session = Depends(get_db)):
    """Mark all new achievements as seen (clear the badge)."""
    db.query(Achievement).filter(Achievement.is_new == True).update({"is_new": False})
    db.commit()
    return {"ok": True}


# ──────────────────────────────────────────────────────────
# Embed code
# ──────────────────────────────────────────────────────────


@app.get("/api/embed-code")
def get_embed_code(request: Request, db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    base_url = settings.public_base_url.rstrip("/")

    js_snippet = f"""<!-- Site Assistant Widget -->
<script
    src="{base_url}/widget-static/saportus-widget.js"
    data-base-url="{base_url}"
></script>"""


    iframe_snippet = f"""<iframe
    src="{base_url}/chat-widget-html?baseUrl={quote(base_url, safe='')}"
    style="position:fixed; bottom:20px; right:20px; width:400px; height:660px; border:none; z-index:9999; background:transparent;"
    title="{s.bot_name if s else 'Помощник'}">
</iframe>"""

    return {"jsSnippet": js_snippet, "iframeSnippet": iframe_snippet}


# ──────────────────────────────────────────────────────────
# Widget endpoints
# ──────────────────────────────────────────────────────────
@app.get("/api/widget-config")
def get_actual_bot_config(request: Request, db: Session = Depends(get_db)):

    # for: backend/widget-static/saportus-widget.js
    #      backend/widget-static/saportus-widget-iframe.html

    s = db.query(SettingsModel).first()
    return {
        "bot_name": s.bot_name if s else "САПОРТУС",
        "accent_color": s.accent_color if s else  "#8000ff",
        "welcome_message": s.welcome_message if s else  "Привет! Чем могу помочь?",
        "chat_bg_color": s.chat_bg_color if s else  "#f8f9fb",
        "user_bubble_bg": s.user_bubble_bg if s else  "#01696f",
        "user_text_color": s.user_text_color if s else  "#ffffff",
        "bot_bubble_bg": s.bot_bubble_bg if s else  "#ffffff",
        "bot_text_color": s.bot_text_color if s else  "#222222",
    }



@app.get("/chat-widget-html", response_class=HTMLResponse)
def serve_chat_widget(request: Request):
    html = (WIDGET_STATIC_DIR / "saportus-widget-iframe.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


# ──────────────────────────────────────────────────────────
# Serve React frontend (production)
# ──────────────────────────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(_: str):
        index = os.path.join(FRONTEND_DIST, "index.html")
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
