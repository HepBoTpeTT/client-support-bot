# Временный патч: заменяем MySQL на SQLite для тестовой среды
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os

# SQLite для тестов
DB_PATH = "/tmp/site_assistant_test.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
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
    from models_test import Settings, Page, Chunk, Dialog, CrawlSession
    Base.metadata.create_all(bind=engine)
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
    finally:
        db.close()
