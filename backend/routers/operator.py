from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, text, and_, or_
from sqlalchemy.orm import Session

from modules.database import get_db
from modules.models import Dialog, Stats
from modules.sse_manager import sse_manager
from modules.ws_manager import ws_manager

router = APIRouter(prefix="/api/operator", tags=["operator"])

ROLE_USER = "user"
ROLE_OPERATOR = "operator"
ROLE_SYSTEM = "system"

EVENT_MESSAGE = "message"
EVENT_HANDOFF_REQUESTED = "handoff_requested"
EVENT_HANDOFF_CLOSED = "handoff_closed"
EVENT_HANDOFF_REOPENED = "handoff_reopened"


# ── Schemas ──────────────────────────────────────────────

class OperatorSendRequest(BaseModel):
    session_id: str
    message: str

class UserOperatorMessageRequest(BaseModel):
    session_id: str
    message: str
    last_id: Optional[int] = 0

class ChatRequest(BaseModel):
    message: str
    session_id: str


# ── Helpers ───────────────────────────────────────────────

def happened_after(row: Dialog):
    return or_(
        Dialog.created_at > row.created_at,
        and_(Dialog.created_at == row.created_at, Dialog.id > row.id),
    )


def get_operator_status(session_id: str, db: Session) -> str:
    last_start = (
        db.query(Dialog)
        .filter(
            Dialog.session_id == session_id,
            Dialog.event_type.in_([EVENT_HANDOFF_REQUESTED, EVENT_HANDOFF_REOPENED]),
        )
        .order_by(desc(Dialog.created_at), desc(Dialog.id))
        .first()
    )
    if not last_start:
        return "none"

    has_close = db.query(Dialog).filter(
        Dialog.session_id == session_id,
        Dialog.event_type == EVENT_HANDOFF_CLOSED,
        happened_after(last_start),
    ).count() > 0

    if has_close:
        return "closed"

    has_reply = db.query(Dialog).filter(
        Dialog.session_id == session_id,
        Dialog.role == ROLE_OPERATOR,
        Dialog.event_type == EVENT_MESSAGE,
        happened_after(last_start),
    ).count() > 0

    return "active" if has_reply else "pending"


def get_operator_preview_text(d: Dialog | None) -> str:
    if not d:
        return ""
    if d.event_type == EVENT_HANDOFF_REQUESTED:
        return "Запрошен оператор"
    if d.event_type == EVENT_HANDOFF_REOPENED:
        return "Обращение открыто повторно"
    if d.event_type == EVENT_HANDOFF_CLOSED:
        return "Обращение закрыто"
    text_val = (d.content or "").strip()
    if d.role == ROLE_OPERATOR:
        return f"Оператор: {text_val[:120]}"
    return text_val[:120]


# ── Routes ────────────────────────────────────────────────

@router.post("/request")
async def request_operator(req: ChatRequest, db: Session = Depends(get_db)):
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

    next_event = (
        EVENT_HANDOFF_REOPENED
        if last_event and last_event.event_type == EVENT_HANDOFF_CLOSED
        else EVENT_HANDOFF_REQUESTED
    )

    db.execute(text("""
        UPDATE stats
        SET total_operator_requested = total_operator_requested + (
            CASE
                WHEN :session_id LIKE 'sess%%'
                AND NOT EXISTS (
                    SELECT 1 FROM dialogs
                    WHERE session_id = :session_id
                    AND event_type IN ('handoff_requested', 'handoff_reopened')
                )
                THEN 1 ELSE 0
            END
        )
        WHERE id = 1
    """), {"session_id": req.session_id})

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
    await sse_manager.broadcast("operator_sessions_updated", None)
    return {"ok": True, "status": "pending"}


@router.post("/user-message")
async def user_operator_message(req: UserOperatorMessageRequest, db: Session = Depends(get_db)):
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

    await sse_manager.broadcast("operator_sessions_updated", None)
    await ws_manager.send_to_room(req.session_id, {
        "type": "user_message",
        "content": req.message.strip(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


@router.get("/sessions")
def get_operator_sessions(db: Session = Depends(get_db)):
    now_utc = datetime.now(timezone.utc)
    since = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    from sqlalchemy import func
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
            Dialog.created_at >= since,
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

        last_msg = (
            db.query(Dialog)
            .filter(Dialog.session_id == row.session_id, Dialog.role == ROLE_USER)
            .order_by(desc(Dialog.created_at), desc(Dialog.id))
            .first()
        )

        user_msg_count = db.query(Dialog).filter(
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
            "userMessageCount": user_msg_count,
        })

    return result


@router.get("/messages/{session_id}")
def get_operator_messages(session_id: str, db: Session = Depends(get_db)):
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


@router.get("/poll/{session_id}")
def poll_operator_messages(session_id: str, last_id: int = 0, db: Session = Depends(get_db)):
    """Fallback polling для виджета (используется если WS недоступен)."""
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


@router.post("/send")
async def operator_send(req: OperatorSendRequest, db: Session = Depends(get_db)):
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

    db.execute(text("""
        UPDATE stats
        SET total_operator_answered = total_operator_answered + (
            CASE
                WHEN :session_id LIKE 'sess%%'
                AND NOT EXISTS (
                    SELECT 1 FROM dialogs
                    WHERE session_id = :session_id
                    AND role = 'operator'
                    AND event_type = 'message'
                )
                THEN 1 ELSE 0
            END
        )
        WHERE id = 1
    """), {"session_id": req.session_id})

    db.add(Dialog(
        session_id=req.session_id,
        role=ROLE_OPERATOR,
        event_type=EVENT_MESSAGE,
        content=req.message.strip(),
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    await sse_manager.broadcast("operator_sessions_updated", None)
    await ws_manager.send_to_room(req.session_id, {
        "type": "operator_message",
        "content": req.message.strip(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


@router.patch("/sessions/{session_id}")
async def update_operator_session(session_id: str, db: Session = Depends(get_db)):
    status = get_operator_status(session_id, db)
    if status == "none":
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    if status == "closed":
        next_event, next_status = EVENT_HANDOFF_REOPENED, "pending"
    else:
        next_event, next_status = EVENT_HANDOFF_CLOSED, "closed"

    db.add(Dialog(
        session_id=session_id,
        role=ROLE_SYSTEM,
        event_type=next_event,
        content=None,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    await sse_manager.broadcast("operator_sessions_updated", None)
    await ws_manager.send_to_room(session_id, {
        "type": "status_update",
        "status": next_status,
    })
    return {"ok": True, "status": next_status}
