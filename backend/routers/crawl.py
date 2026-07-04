import asyncio
import logging
import threading
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from modules.crawler import crawl_site
from modules.database import get_db, SessionLocal
from modules.models import CrawlSession, Settings as SettingsModel
from modules.sse_manager import sse_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["crawl"])


# ── Schemas ──────────────────────────────────────────────

class CrawlStartRequest(BaseModel):
    url: str


# ── Helpers ───────────────────────────────────────────────

def session_to_dict(s: CrawlSession) -> dict:
    return {
        "id": s.id,
        "targetUrl": s.target_url,
        "status": s.status,
        "pagesFound": s.pages_found,
        "pagesDone": s.pages_done,
        "startedAt": s.started_at.isoformat() if s.started_at else None,
        "finishedAt": s.finished_at.isoformat() if s.finished_at else None,
        "errorMessage": s.error_message,
    }


# ── Routes ────────────────────────────────────────────────

@router.post("/crawl/start")
async def start_crawl(
    req: CrawlStartRequest,
    db: Session = Depends(get_db),
):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL required")

    running = (
        db.query(CrawlSession)
        .filter(CrawlSession.status == "running")
        .order_by(desc(CrawlSession.id))
        .first()
    )
    if running:
        raise HTTPException(status_code=409, detail="Crawling already started")

    session = CrawlSession(
        target_url=url,
        status="running",
        pages_found=0,
        pages_done=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session_id = session.id

    s = db.query(SettingsModel).first()
    if s:
        s.target_url = url
        db.commit()
    
    await sse_manager.broadcast("crawl_progress", {"status": "started"})

    # Сохраняем loop ДО запуска треда
    _loop = asyncio.get_event_loop()

    def run_crawl_sync():
        crawldb = SessionLocal()
        try:
            crawl_site(session_id, url, crawldb, _loop)

            sess = crawldb.get(CrawlSession, session_id)
            pages_done = sess.pages_done if sess else 0
            crawldb.execute(
                text("""
                    UPDATE stats
                    SET total_crawl_runs = total_crawl_runs + 1,
                        max_pages_in_run = GREATEST(max_pages_in_run, :pages)
                    WHERE id = 1
                """),
                {"pages": pages_done},
            )
            crawldb.commit()

            asyncio.run_coroutine_threadsafe(
                sse_manager.broadcast("crawl_progress", {"status": "done"}),
                _loop
            )

        except Exception as e:
            logger.error(f"Crawl error: {e}\n{traceback.format_exc()}")
            sess = crawldb.get(CrawlSession, session_id)
            if sess:
                sess.status = "error"
                sess.error_message = str(e)
                sess.finished_at = datetime.now(timezone.utc)
                crawldb.commit()
            asyncio.run_coroutine_threadsafe(
                sse_manager.broadcast("crawl_progress", {"status": "error"}),
                _loop
            )
        finally:
            crawldb.close()

    threading.Thread(target=run_crawl_sync, daemon=True).start()
    return {"sessionId": session_id, "status": "running"}


@router.get("/crawl/status")
def get_crawl_status(db: Session = Depends(get_db)):
    session = (
        db.query(CrawlSession)
        .filter(CrawlSession.status == "running")
        .order_by(desc(CrawlSession.id))
        .first()
    ) or db.query(CrawlSession).order_by(desc(CrawlSession.id)).first()

    if not session:
        return {"status": "idle"}

    return session_to_dict(session)


@router.get("/crawl/sessions")
def get_crawl_sessions(db: Session = Depends(get_db)):
    sessions = db.query(CrawlSession).order_by(desc(CrawlSession.id)).all()
    return [session_to_dict(s) for s in sessions]


@router.delete("/crawl/sessions")
async def delete_crawl_history(db: Session = Depends(get_db)):
    db.query(CrawlSession).delete()
    db.commit()
    await sse_manager.broadcast("crawl_progress", {"status": "idle"})
    return {"ok": True}
