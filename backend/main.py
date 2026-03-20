import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from config import settings
from database import get_db, init_db
from models import Settings as SettingsModel, Page, Chunk, Dialog, CrawlSession, OperatorSession, OperatorMessage, Achievement, DailyTask
from crawler import crawl_site, search_chunks
from widget import generate_widget_js, generate_chat_widget_html

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Отключаем избыточные логи httpx и hpack
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrate: add chat_bg_color BEFORE init_db reads the table
    try:
        from database import engine as _engine
        import sqlalchemy as _sa
        with _engine.connect() as _conn:
            _conn.execute(_sa.text(
                "ALTER TABLE settings ADD COLUMN chat_bg_color VARCHAR(32) DEFAULT '#f8f9fb'"
            ))
            _conn.commit()
            logger.info("Migrated: added chat_bg_color column")
    except Exception:
        pass  # Column already exists or table doesn't exist yet
    init_db()
    logger.info("Database initialized")
    # Автоочистка: если бэк был прерван на середине парсинга —
    # сессии висят в running. Сбрасываем их при каждом запуске.
    try:
        from database import SessionLocal
        from datetime import datetime
        _db = SessionLocal()
        stale = _db.query(CrawlSession).filter(CrawlSession.status == "running").all()
        for s in stale:
            s.status = "error"
            s.error_message = "Бэкенд был перезапущен во время парсинга"
            s.finished_at = datetime.now()
        if stale:
            _db.commit()
            logger.warning(f"Сброшено {len(stale)} зависших сессий парсинга")
        _db.close()
    except Exception as e:
        logger.error(f"Ошибка при очистке сессий: {e}")

    # Start background thread: auto-clean inactive chat sessions every 15 min
    def _auto_clean_dialogs():
        import time
        while True:
            time.sleep(900)  # 15 minutes
            try:
                from database import SessionLocal as _SL
                from datetime import timedelta
                _db2 = _SL()
                cutoff = datetime.now() - timedelta(hours=1)
                # Find session_ids with last message older than 1h
                old_sessions = (
                    _db2.query(Dialog.session_id)
                    .group_by(Dialog.session_id)
                    .having(func.max(Dialog.created_at) < cutoff)
                    .all()
                )
                if old_sessions:
                    ids = [r[0] for r in old_sessions]
                    _db2.query(Dialog).filter(Dialog.session_id.in_(ids)).delete(synchronize_session=False)
                    _db2.commit()
                    logger.info(f"Авто-очистка: удалено {len(ids)} неактивных сессий чата")
                _db2.close()
            except Exception as ex:
                logger.error(f"auto_clean_dialogs error: {ex}")

    threading.Thread(target=_auto_clean_dialogs, daemon=True).start()
    yield


app = FastAPI(title="Site Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    # snake_case (direct)
    openai_key: Optional[str] = None
    bot_name: Optional[str] = None
    welcome_message: Optional[str] = None
    accent_color: Optional[str] = None
    language: Optional[str] = None
    target_url: Optional[str] = None
    model: Optional[str] = None
    # camelCase (from frontend)
    openaiKey: Optional[str] = None
    botName: Optional[str] = None
    welcomeMessage: Optional[str] = None
    accentColor: Optional[str] = None
    targetUrl: Optional[str] = None
    chatBgColor: Optional[str] = None


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
        "targetUrl": s.target_url,
        "model": s.model,
        "chatBgColor": getattr(s, "chat_bg_color", "#f8f9fb") or "#f8f9fb",
    }


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

    # Map both camelCase and snake_case keys to model fields
    field_map = {
        "openai_key": "openai_key",
        "openaiKey": "openai_key",
        "bot_name": "bot_name",
        "botName": "bot_name",
        "welcome_message": "welcome_message",
        "welcomeMessage": "welcome_message",
        "accent_color": "accent_color",
        "accentColor": "accent_color",
        "language": "language",
        "target_url": "target_url",
        "targetUrl": "target_url",
        "model": "model",
        "chat_bg_color": "chat_bg_color",
        "chatBgColor": "chat_bg_color",
    }

    for field, value in update_data.items():
        # Don't overwrite with masked value
        if field in ("openai_key", "openaiKey") and value.startswith("••••"):
            continue
        if field in field_map:
            setattr(s, field_map[field], value)

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
        started_at=datetime.now(),
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
        from database import SessionLocal
        crawl_db = SessionLocal()
        try:
            crawl_site(session_id, req.url, crawl_db)
        except Exception as e:
            logger.error(f"Crawl error: {e}")
            sess = crawl_db.get(CrawlSession, session_id)
            if sess:
                sess.status = "error"
                sess.error_message = str(e)
                sess.finished_at = datetime.now()
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
    # НЕ загружаем content — он может быть очень большим, фронту он не нужен
    from sqlalchemy import text
    rows = db.execute(text(
        "SELECT id, url, title, status, crawled_at FROM pages ORDER BY id"
    )).fetchall()
    return [
        {
            "id": r[0],
            "url": r[1],
            "title": r[2],
            "status": r[3],
            "crawledAt": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


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
    db.query(Chunk).delete()
    db.query(Page).delete()
    db.commit()
    return {"ok": True}


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

    # Save user message
    db.add(Dialog(session_id=req.session_id, role="user", content=req.message, created_at=datetime.now()))
    db.commit()

    # RAG: find relevant chunks
    relevant_chunks = search_chunks(db, req.message, limit=5)
    if relevant_chunks:
        context = "\n\n---\n\n".join(
            f"[Источник: {c.page_title} ({c.page_url})]\n{c.chunk_text}"
            for c in relevant_chunks
        )
    else:
        context = "База знаний пуста. Ответь на основе общих знаний."

    # Get recent conversation history
    history = (
        db.query(Dialog)
        .filter(Dialog.session_id == req.session_id)
        .order_by(Dialog.created_at)
        .limit(8)
        .all()
    )

    lang_map = {"ru": "русском", "en": "английском", "uk": "украинском"}
    lang_name = lang_map.get(s.language, s.language)

    system_prompt = (
        f"Ты — {s.bot_name}, вежливый и компетентный AI-помощник сайта.\n"
        f"Отвечай только по теме сайта и его услуг/товаров.\n"
        f"Если вопрос не по теме — вежливо перенаправь.\n"
        f"Отвечай на {lang_name} языке.\n"
        f"Используй следующий контекст из базы знаний сайта:\n\n{context}"
    )

    import httpx
    from openai import AsyncOpenAI
    _proxy = settings.https_proxy or settings.http_proxy or None
    if _proxy:
        # httpx 0.27.x uses 'proxies' dict; 0.28+ uses 'proxy'
        try:
            _http_client = httpx.AsyncClient(proxy=_proxy)
        except TypeError:
            _http_client = httpx.AsyncClient(proxies={"http://": _proxy, "https://": _proxy})
    else:
        _http_client = None
    logger.info(f"OpenAI proxy: {_proxy!r}")
    client = AsyncOpenAI(api_key=s.openai_key, http_client=_http_client)

    messages = [{"role": "system", "content": system_prompt}]
    for d in history[:-1]:  # exclude the last (just saved user msg)
        messages.append({"role": d.role, "content": d.content})
    messages.append({"role": "user", "content": req.message})

    try:
        completion = await client.chat.completions.create(
            model=s.model or "gpt-4o",
            messages=messages,
            max_tokens=800,
            temperature=0.5,
        )
        reply = completion.choices[0].message.content or "Извините, не могу ответить прямо сейчас."
    except Exception as e:
        import traceback
        logger.error(f"OpenAI error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"OpenAI ошибка: {str(e)}")

    # Save assistant reply
    db.add(Dialog(session_id=req.session_id, role="assistant", content=reply, created_at=datetime.now()))
    db.commit()

    return {"reply": reply, "sourcesUsed": len(relevant_chunks)}


# ──────────────────────────────────────────────────────────
# Dialogs
# ──────────────────────────────────────────────────────────

@app.get("/api/dialogs")
def get_dialog_sessions(db: Session = Depends(get_db)):
    # Group by session_id, get latest message and count
    from sqlalchemy import case
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
        last_msg = (
            db.query(Dialog)
            .filter(Dialog.session_id == row.session_id)
            .order_by(desc(Dialog.created_at))
            .first()
        )
        result.append({
            "sessionId": row.session_id,
            "count": row.count,
            "createdAt": row.last_at.isoformat() if row.last_at else None,
            "lastMessage": last_msg.content[:100] if last_msg else "",
        })
    return result


@app.get("/api/dialogs/{session_id}")
def get_session_dialogs(session_id: str, db: Session = Depends(get_db)):
    dialogs = (
        db.query(Dialog)
        .filter(Dialog.session_id == session_id)
        .order_by(Dialog.created_at)
        .all()
    )
    return [
        {
            "id": d.id,
            "sessionId": d.session_id,
            "role": d.role,
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
    existing = db.query(OperatorSession).filter(OperatorSession.session_id == req.session_id).first()
    if existing:
        existing.status = "pending"
        db.commit()
        return {"ok": True, "status": "pending"}

    op_session = OperatorSession(
        session_id=req.session_id,
        status="pending",
        created_at=datetime.now(),
    )
    db.add(op_session)
    # Save user message to operator_messages too
    if req.message:
        db.add(OperatorMessage(
            session_id=req.session_id,
            role="user",
            content=req.message,
            created_at=datetime.now(),
        ))
    db.commit()
    return {"ok": True, "status": "pending"}


@app.post("/api/operator/user-message")
def user_operator_message(req: UserOperatorMessageRequest, db: Session = Depends(get_db)):
    """User sends a message while in operator mode."""
    op = db.query(OperatorSession).filter(OperatorSession.session_id == req.session_id).first()
    if not op or op.status == "closed":
        raise HTTPException(status_code=400, detail="Нет активной сессии с оператором")
    db.add(OperatorMessage(
        session_id=req.session_id,
        role="user",
        content=req.message,
        created_at=datetime.now(),
    ))
    db.commit()
    return {"ok": True}


@app.get("/api/operator/sessions")
def get_operator_sessions(db: Session = Depends(get_db)):
    """Admin: list all operator sessions with last message."""
    sessions = db.query(OperatorSession).order_by(desc(OperatorSession.updated_at)).all()
    result = []
    for s in sessions:
        last_msg = (
            db.query(OperatorMessage)
            .filter(OperatorMessage.session_id == s.session_id)
            .order_by(desc(OperatorMessage.created_at))
            .first()
        )
        unread = (
            db.query(OperatorMessage)
            .filter(
                OperatorMessage.session_id == s.session_id,
                OperatorMessage.role == "user",
            )
            .count()
        )
        result.append({
            "id": s.id,
            "sessionId": s.session_id,
            "status": s.status,
            "createdAt": s.created_at.isoformat() if s.created_at else None,
            "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
            "lastMessage": last_msg.content[:120] if last_msg else "",
            "lastMessageRole": last_msg.role if last_msg else "",
            "userMessageCount": unread,
        })
    return result


@app.get("/api/operator/messages/{session_id}")
def get_operator_messages(session_id: str, db: Session = Depends(get_db)):
    """Get all operator chat messages for a session."""
    msgs = (
        db.query(OperatorMessage)
        .filter(OperatorMessage.session_id == session_id)
        .order_by(OperatorMessage.created_at)
        .all()
    )
    return [
        {
            "id": m.id,
            "sessionId": m.session_id,
            "role": m.role,
            "content": m.content,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


@app.get("/api/operator/poll/{session_id}")
def poll_operator_messages(session_id: str, last_id: int = 0, db: Session = Depends(get_db)):
    """Widget polling: get new operator messages since last_id."""
    op = db.query(OperatorSession).filter(OperatorSession.session_id == session_id).first()
    if not op:
        return {"status": "none", "messages": []}
    msgs = (
        db.query(OperatorMessage)
        .filter(
            OperatorMessage.session_id == session_id,
            OperatorMessage.id > last_id,
            OperatorMessage.role == "operator",
        )
        .order_by(OperatorMessage.created_at)
        .all()
    )
    return {
        "status": op.status,
        "messages": [
            {"id": m.id, "content": m.content, "createdAt": m.created_at.isoformat()}
            for m in msgs
        ],
    }


@app.post("/api/operator/send")
def operator_send(req: OperatorSendRequest, db: Session = Depends(get_db)):
    """Admin/operator sends message to user."""
    op = db.query(OperatorSession).filter(OperatorSession.session_id == req.session_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    if op.status == "pending":
        op.status = "active"
    op.updated_at = datetime.now()
    db.add(OperatorMessage(
        session_id=req.session_id,
        role="operator",
        content=req.message,
        created_at=datetime.now(),
    ))
    db.commit()
    return {"ok": True}


@app.patch("/api/operator/sessions/{session_id}")
def update_operator_session(session_id: str, db: Session = Depends(get_db)):
    """Close/reopen an operator session."""
    op = db.query(OperatorSession).filter(OperatorSession.session_id == session_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    op.status = "closed" if op.status != "closed" else "active"
    op.updated_at = datetime.now()
    db.commit()
    return {"ok": True, "status": op.status}


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
    db.add(Achievement(key=key, unlocked_at=datetime.now(), is_new=True))
    db.commit()
    return True


def check_achievements(db: Session) -> list[str]:
    """Re-evaluate all threshold achievements. Returns list of newly unlocked keys."""
    newly = []

    crawl_count = db.query(CrawlSession).filter(CrawlSession.status == "done").count()
    last_crawl = db.query(CrawlSession).filter(CrawlSession.status == "done").order_by(desc(CrawlSession.id)).first()
    max_pages = last_crawl.pages_done if last_crawl else 0

    dialog_sessions = db.query(Dialog.session_id).distinct().count()
    total_messages = db.query(Dialog).filter(Dialog.role == "user").count()
    operator_sessions = db.query(OperatorSession).count()
    s = db.query(SettingsModel).first()

    checks = [
        ("first_crawl",         crawl_count >= 1),
        ("crawl_5",              crawl_count >= 5),
        ("crawl_20",             crawl_count >= 20),
        ("pages_10",             max_pages >= 10),
        ("pages_50",             max_pages >= 50),
        ("pages_200",            max_pages >= 200),
        ("first_dialog",         dialog_sessions >= 1),
        ("dialogs_10",           dialog_sessions >= 10),
        ("dialogs_50",           dialog_sessions >= 50),
        ("dialogs_200",          dialog_sessions >= 200),
        ("messages_100",         total_messages >= 100),
        ("messages_1000",        total_messages >= 1000),
        ("first_operator",       operator_sessions >= 1),
        ("operator_10",          operator_sessions >= 10),
        ("operator_50",          operator_sessions >= 50),
        ("settings_configured",  bool(s and s.openai_key and s.bot_name and s.target_url)),
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
    today = datetime.now().strftime("%Y-%m-%d")
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
    pending_operators = db.query(OperatorSession).filter(
        OperatorSession.status == "pending"
    ).count()

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
    today = datetime.now().strftime("%Y-%m-%d")
    exists = db.query(DailyTask).filter(
        DailyTask.task_key == req.task_key,
        DailyTask.completed_date == today,
    ).first()
    if not exists:
        db.add(DailyTask(task_key=req.task_key, completed_date=today, completed_at=datetime.now()))
        db.commit()

        # Check streak achievements
        # Count distinct dates with ALL tasks completed
        all_keys = {t["key"] for t in DAILY_TASK_DEFS}
        # Get all completed dates
        from sqlalchemy import text
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
        from datetime import date, timedelta
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
    host = request.headers.get("host", f"localhost:{settings.port}")
    proto = request.headers.get("x-forwarded-proto", "http")
    base_url = f"{proto}://{host}"

    js_snippet = f"""<!-- Site Assistant Widget -->
<script>
(function(){{
  var s=document.createElement('script');
  s.src='{base_url}/widget.js';
  s.setAttribute('data-bot-name','{s.bot_name if s else "Помощник"}');
  s.setAttribute('data-accent','{s.accent_color if s else "#01696f"}');
  s.setAttribute('data-api','{base_url}/api/chat');
  document.head.appendChild(s);
}})();
</script>"""

    from urllib.parse import quote
    bot_name_enc = quote(s.bot_name if s else "Помощник")
    accent_enc = quote(s.accent_color if s else "#01696f")
    welcome_enc = quote(s.welcome_message if s else "Привет!")
    api_enc = quote(f"{base_url}/api/chat")

    iframe_snippet = f"""<!-- Site Assistant Widget (iFrame) -->
<iframe
  src="{base_url}/chat-widget?botName={bot_name_enc}&accent={accent_enc}&welcome={welcome_enc}&api={api_enc}"
  style="position:fixed;bottom:20px;right:20px;width:400px;height:600px;border:none;z-index:9999;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.18);"
  allow="microphone"
  title="{s.bot_name if s else 'Помощник'}">
</iframe>"""

    return {"jsSnippet": js_snippet, "iframeSnippet": iframe_snippet}


# ──────────────────────────────────────────────────────────
# Widget endpoints
# ──────────────────────────────────────────────────────────

@app.get("/widget.js")
def serve_widget_js(request: Request, db: Session = Depends(get_db)):
    s = db.query(SettingsModel).first()
    host = request.headers.get("host", f"localhost:{settings.port}")
    proto = request.headers.get("x-forwarded-proto", "http")
    api_url = f"{proto}://{host}/api/chat"

    bot_name = s.bot_name if s else "Помощник"
    accent = s.accent_color if s else "#01696f"
    welcome = s.welcome_message if s else "Привет! Чем могу помочь?"
    chat_bg = getattr(s, "chat_bg_color", "#f8f9fb") or "#f8f9fb" if s else "#f8f9fb"

    js = generate_widget_js(bot_name, accent, welcome, api_url, chat_bg)
    return Response(content=js, media_type="application/javascript")


@app.get("/chat-widget", response_class=HTMLResponse)
def serve_chat_widget(
    request: Request,
    botName: str = "Помощник",
    accent: str = "#01696f",
    welcome: str = "Привет! Чем могу помочь?",
    api: str = "",
    db: Session = Depends(get_db),
):
    if not api:
        host = request.headers.get("host", f"localhost:{settings.port}")
        proto = request.headers.get("x-forwarded-proto", "http")
        api = f"{proto}://{host}/api/chat"
    s = db.query(SettingsModel).first()
    chat_bg = getattr(s, "chat_bg_color", "#f8f9fb") or "#f8f9fb" if s else "#f8f9fb"
    html = generate_chat_widget_html(botName, accent, welcome, api, chat_bg)
    return HTMLResponse(content=html)


# ──────────────────────────────────────────────────────────
# Serve React frontend (production)
# ──────────────────────────────────────────────────────────
import os
from fastapi.staticfiles import StaticFiles

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        from fastapi.responses import FileResponse
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
