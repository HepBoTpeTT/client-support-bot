import logging
import traceback
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings as app_settings
from modules.crawler import search_chunks
from modules.database import get_db
from modules.models import Dialog, Settings as SettingsModel
from modules.qdrant_store import search_similar
from modules.sse_manager import sse_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
EVENT_MESSAGE = "message"


class ChatRequest(BaseModel):
    message: str
    session_id: str


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def build_system_prompt(s: SettingsModel, context: str) -> str:
    lang_map = {"ru": "русском", "en": "английском", "uk": "украинском"}
    template = (s.system_prompt or "").strip()
    if not template:
        template = (
            "Ты — {bot_name}, вежливый и компетентный AI-помощник сайта.\n"
            "Отвечай только по теме сайта и его услуг/товаров.\n"
            "Если вопрос не по теме — вежливо перенаправь.\n"
            "Отвечай на {language} языке.\n"
            "Используй следующий контекст из базы знаний сайта:\n"
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


@router.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    if not req.message or not req.session_id:
        raise HTTPException(status_code=400, detail="message и session_id обязательны")

    s = db.query(SettingsModel).first()

    # Записываем сообщение пользователя сразу — до любых проверок
    db.execute(text("""
        UPDATE stats
        SET total_user_messages = total_user_messages + 1,
            total_dialog_sessions = total_dialog_sessions + (
                CASE
                    WHEN :session_id LIKE 'sess%%'
                    AND NOT EXISTS (
                        SELECT 1 FROM dialogs WHERE session_id = :session_id
                    )
                    THEN 1 ELSE 0
                END
            )
        WHERE id = 1
    """), {"session_id": req.session_id})

    db.add(Dialog(
        session_id=req.session_id,
        role=ROLE_USER,
        event_type=EVENT_MESSAGE,
        content=req.message,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    await sse_manager.broadcast("dialogs_updated", None)

    reply = "Извините, сейчас временно не удаётся получить ответ. Попробуйте позже или обратитесь к оператору."
    relevant_chunks = []
    retrieval_backend = "none"

    # Нет ключа — пишем fallback в БД и возвращаем его
    if not s or not s.openai_key:
        logger.warning(f"OpenAI key not configured for session {req.session_id}")
    else:
        # История для контекста
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

        # RAG поиск
        try:
            relevant_chunks = search_similar(req.message, limit=5)
            retrieval_backend = "qdrant"
        except Exception as e:
            logger.warning(f"Qdrant failed, fallback to MySQL: {e}")
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
                logger.error(f"MySQL fallback failed: {e2}")

        context = (
            "\n\n---\n\n".join(
                f"[Источник: {c['page_title']} ({c['page_url']})]\\n{c['chunk_text']}"
                for c in relevant_chunks
            )
            if relevant_chunks
            else "База знаний пуста. Ответь на основе общих знаний."
        )

        system_prompt = build_system_prompt(s, context)

        _proxy = app_settings.openai_proxy or app_settings.http_proxy or None
        if _proxy:
            try:
                _http_client = httpx.AsyncClient(proxy=_proxy)
            except TypeError:
                _http_client = httpx.AsyncClient(proxies={"http://": _proxy, "https://": _proxy})
        else:
            _http_client = None

        client = AsyncOpenAI(api_key=s.openai_key, http_client=_http_client)

        messages = [{"role": "system", "content": system_prompt}]
        for d in history:
            messages.append({"role": d.role, "content": d.content})
        messages.append({"role": "user", "content": req.message})

        try:
            completion = await client.chat.completions.create(
                model=s.model or "gpt-4o",
                messages=messages,
                max_tokens=800,
                temperature=0.5,
            )
            reply = completion.choices[0].message.content or reply
        except Exception as e:
            logger.error(f"OpenAI error: {traceback.format_exc()}")

    # Записываем ответ бота в любом случае
    db.add(Dialog(
        session_id=req.session_id,
        role=ROLE_ASSISTANT,
        content=reply,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    await sse_manager.broadcast("dialogs_updated", None)

    return {
        "reply": reply,
        "sourcesUsed": len(relevant_chunks),
        "retrievalBackend": retrieval_backend,
    }
