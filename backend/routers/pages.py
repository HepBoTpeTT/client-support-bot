import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.database import get_db
from modules.models import Page, Chunk
from modules.qdrant_store import clear_collection
from modules.sse_manager import sse_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["pages"])


@router.get("/pages")
def get_pages(db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT id, url, title, status, crawled_at, CHAR_LENGTH(content) AS content_len FROM pages ORDER BY id"
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


@router.get("/pages/{page_id}/content")
def get_page_content(page_id: int, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"content": page.content}


@router.delete("/pages/{page_id}")
async def delete_page(page_id: int, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    db.delete(page)
    db.commit()
    await sse_manager.broadcast("pages_updated", None)
    return {"ok": True}


@router.delete("/pages")
async def clear_pages(db: Session = Depends(get_db)):
    try:
        db.query(Chunk).delete()
        db.query(Page).delete()
        db.commit()
        clear_collection()
        await sse_manager.broadcast("pages_updated", None)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Clear pages error: {e}")
        return {"ok": False}
