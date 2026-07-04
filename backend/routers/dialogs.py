from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from modules.database import get_db
from modules.models import Dialog

from modules.sse_manager import sse_manager

router = APIRouter(prefix="/api", tags=["dialogs"])

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_OPERATOR = "operator"


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
        if d.role == ROLE_OPERATOR:
            return f"Оператор: {(d.content or '').strip()[:100]}"
        if d.role == ROLE_ASSISTANT:
            return f"Бот: {(d.content or '').strip()[:100]}"
        return (d.content or "").strip()[:100]
    return "Системное событие"


@router.get("/dialogs")
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
            .filter(Dialog.session_id == row.session_id, Dialog.role == ROLE_USER)
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


@router.get("/dialogs/{session_id}")
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


@router.delete("/dialogs/{session_id}")
async def delete_dialog_session(session_id: str, db: Session = Depends(get_db)):
    from routers.operator import get_operator_status
    status = get_operator_status(session_id, db)
    if status in ("pending", "active"):
        raise HTTPException(status_code=409, detail="Нельзя удалить диалог с активной сессией оператора")
    db.query(Dialog).filter(Dialog.session_id == session_id).delete()
    db.commit()
    await sse_manager.broadcast("operator_sessions_updated", None)
    await sse_manager.broadcast("dialogs_updated", None)
    return {"ok": True}


@router.delete("/dialogs")
async def delete_all_dialogs(db: Session = Depends(get_db)):
    from routers.operator import get_operator_status
    active_sessions = db.query(Dialog.session_id).distinct().all()
    for (sid,) in active_sessions:
        if get_operator_status(sid, db) in ("pending", "active"):
            raise HTTPException(status_code=409, detail="Нельзя удалить диалоги — есть активные сессии оператора")
    db.query(Dialog).delete()
    db.commit()
    await sse_manager.broadcast("operator_sessions_updated", None)
    await sse_manager.broadcast("dialogs_updated", None)
    return {"ok": True}
