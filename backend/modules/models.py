from datetime import datetime
from sqlalchemy import (
    Integer, String, Text, DateTime, ForeignKey, func, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openai_key: Mapped[str] = mapped_column(Text, default="")
    crawler_settings: Mapped[str] = mapped_column(Text, default="script style noscript svg iframe nav header footer aside button form input select")
    language: Mapped[str] = mapped_column(String(16), default="ru")
    target_url: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(64), default="gpt-4o")
    bot_name: Mapped[str] = mapped_column(String(255), default="Помощник")
    welcome_message: Mapped[str] = mapped_column(Text, default="Привет! Чем могу помочь?")
    system_prompt: Mapped[str] = mapped_column(Text, default=
            "Ты — {bot_name}, вежливый и компетентный AI-помощник сайта.\n"
            "Отвечай только по теме сайта и его услуг/товаров.\n"
            "Если вопрос не по теме — вежливо перенаправь.\n"
            "Отвечай на {language} языке.\n"
            "Используй следующий контекст из базы знаний сайта:\n\n"
            "{context}"
        )
    accent_color: Mapped[str] = mapped_column(String(32), default="#01696f")
    chat_bg_color: Mapped[str] = mapped_column(String(32), default="#f8f9fb")
    user_bubble_bg: Mapped[str] = mapped_column(String(32), default="#01696f")
    user_text_color: Mapped[str] = mapped_column(String(32), default="#ffffff")
    bot_bubble_bg: Mapped[str] = mapped_column(String(32), default="#ffffff")
    bot_text_color: Mapped[str] = mapped_column(String(32), default="#222222")


class CrawlSession(Base):
    __tablename__ = "crawl_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running")
    pages_found: Mapped[int] = mapped_column(Integer, default=0)
    pages_done: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=False)  # unique enforced in logic
    title: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text(16777215), default="")  # MEDIUMTEXT
    status: Mapped[str] = mapped_column(String(32), default="pending")
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="page", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(Integer, ForeignKey("pages.id", ondelete="CASCADE"))
    page_url: Mapped[str] = mapped_column(Text)
    page_title: Mapped[str] = mapped_column(String(512), default="")
    chunk_text: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)

    page: Mapped["Page"] = relationship("Page", back_populates="chunks")


class Dialog(Base):
    __tablename__ = "dialogs"
    __table_args__ = (
        Index("ix_dialogs_session_created", "session_id", "created_at"),
        Index("ix_dialogs_event_type_created", "event_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="user")  # user | assistant | operator | system
    event_type: Mapped[str] = mapped_column(String(32), default="message")
    content: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Achievement(Base):
    """Unlocked achievements for this installation."""
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)  # e.g. "first_crawl"
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    is_new: Mapped[bool] = mapped_column(Integer, default=1)   # 1 = unseen badge


class DailyTask(Base):
    """Daily task completion log."""
    __tablename__ = "daily_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(String(64))          # e.g. "check_dialogs"
    completed_date: Mapped[str] = mapped_column(String(16))    # YYYY-MM-DD
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Stats(Base):
    __tablename__ = "stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Crawler
    total_crawl_runs: Mapped[int] = mapped_column(Integer, default=0)
    max_pages_in_run: Mapped[int] = mapped_column(Integer, default=0)
    # Dialogs
    total_dialog_sessions: Mapped[int] = mapped_column(Integer, default=0)
    total_user_messages: Mapped[int] = mapped_column(Integer, default=0)
    # Operator
    total_operator_requested: Mapped[int] = mapped_column(Integer, default=0)
    total_operator_answered: Mapped[int] = mapped_column(Integer, default=0)
