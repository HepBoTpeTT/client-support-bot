import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Шаг 1: убеждаемся что база данных существует
# Подключаемся БЕЗ указания имени БД и создаём её если нет.
# Retry нужен потому что MySQL-контейнер может ещё подниматься.
# ──────────────────────────────────────────────────────────

def ensure_database_exists(retries: int = 10, delay: float = 3.0) -> None:
    url_without_db = (
        f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/"
        f"?charset=utf8mb4"
    )
    for attempt in range(1, retries + 1):
        try:
            tmp = create_engine(url_without_db, echo=False)
            with tmp.connect() as conn:
                conn.execute(text(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
            tmp.dispose()
            logger.info(f"Database '{settings.mysql_database}' ready")
            return
        except Exception as e:
            logger.warning(f"MySQL not ready (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError(
        f"MySQL не поднялся за {retries * delay:.0f}с — проверьте подключение"
    )


ensure_database_exists()


# ──────────────────────────────────────────────────────────
# Шаг 2: engine и сессии — после того как БД точно существует
# ──────────────────────────────────────────────────────────

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,   # проверяет соединение перед использованием
    pool_recycle=3600,    # переоткрывает соединения раз в час
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — даёт сессию БД и закрывает её после запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────────────────────────────────
# Шаг 3: init_db — создаёт таблицы и сидирует начальные данные
#
# Вызывается из lifespan ПОСЛЕ миграций.
# Qdrant инициализируется отдельно и не прерывает создание таблиц.
# ──────────────────────────────────────────────────────────

def init_db() -> None:
    # Импорт моделей внутри функции — чтобы Base.metadata знал о всех таблицах
    from .models import Settings, Page, Chunk, Dialog, CrawlSession, Achievement, DailyTask, Stats  # noqa: F401

    # Создаём все таблицы которых ещё нет (идемпотентно)
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created/exist")

    # Сидируем начальные данные
    db = SessionLocal()
    try:
        if not db.query(Settings).first():
            db.add(Settings(
                openai_key="",
                bot_name="Помощник",
                welcome_message="Привет! Чем могу помочь?",
                language="ru",
                target_url="",
                model="gpt-4o",
                accent_color="#01696f",
                chat_bg_color="#f8f9fb",
                user_bubble_bg="#01696f",
                user_text_color="#ffffff",
                bot_bubble_bg="#ffffff",
                bot_text_color="#222222",
            ))
            db.commit()
            logger.info("Default settings seeded")

        if not db.query(Stats).filter(Stats.id == 1).first():
            db.add(Stats(id=1))
            db.commit()
            logger.info("Default stats row seeded")

    except Exception as e:
        logger.error(f"Seed error: {e}")
        db.rollback()
    finally:
        db.close()

    # Qdrant — некритично, не ломаем старт если недоступен
    try:
        from .qdrant_store import init_collection
        init_collection()
        logger.info("Qdrant collection ready")
    except Exception as e:
        logger.warning(f"Qdrant init failed (non-critical): {e}")
