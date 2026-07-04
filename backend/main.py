import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from modules.database import engine, init_db, SessionLocal
from modules.models import CrawlSession

from routers import settings, crawl, pages, dialogs, operator, chat, gamification, widget, realtime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Создаём таблицы и сидируем данные
    init_db()
    logger.info("Database initialized")

    # 2. Сбрасываем зависшие сессии парсинга
    try:
        db = SessionLocal()
        stale = db.query(CrawlSession).filter(CrawlSession.status == "running").all()
        for s in stale:
            s.status = "error"
            s.error_message = "Бэкенд был перезапущен во время парсинга"
            s.finished_at = datetime.now(timezone.utc)
        if stale:
            db.commit()
            logger.warning(f"Сброшено {len(stale)} зависших сессий парсинга")
        db.close()
    except Exception as e:
        logger.error(f"Ошибка при очистке сессий: {e}")

    yield


app = FastAPI(title="Saportus API", lifespan=lifespan)

# ── Middleware ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files ──────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

# ── Routers ───────────────────────────────────────────────
app.include_router(settings.router)
app.include_router(crawl.router)
app.include_router(pages.router)
app.include_router(dialogs.router)
app.include_router(operator.router)
app.include_router(chat.router)
app.include_router(gamification.router)
app.include_router(widget.router)
app.include_router(realtime.router)

# ── SPA (production) ──────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(_: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    from config import settings as app_settings
    uvicorn.run("main:app", host=app_settings.host, port=app_settings.port, reload=app_settings.debug)
