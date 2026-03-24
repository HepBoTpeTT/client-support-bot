from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import Settings, Page, Chunk, Dialog, CrawlSession  # noqa
    from qdrant_store import init_collection
    Base.metadata.create_all(bind=engine)

    # Seed default settings if empty
    db = SessionLocal()
    try:
        if not db.query(Settings).first():
            db.add(Settings(
                openai_key="",
                bot_name="Помощник",
                welcome_message="Привет! Чем могу помочь?",
                accent_color="#01696f",
                language="ru",
                target_url="",
                model="gpt-4o",
            ))
            db.commit()
            logger.info("Default settings seeded")
    finally:
        db.close()
    init_collection()
