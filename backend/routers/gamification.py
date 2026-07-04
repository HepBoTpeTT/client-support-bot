from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from modules.database import get_db
from modules.models import Achievement, DailyTask, Dialog, Settings as SettingsModel, Stats
from modules.sse_manager import sse_manager

router = APIRouter(prefix="/api/gamification", tags=["gamification"])

ROLE_OPERATOR = "operator"
EVENT_MESSAGE = "message"
EVENT_HANDOFF_REQUESTED = "handoff_requested"
EVENT_HANDOFF_REOPENED = "handoff_reopened"

ACHIEVEMENT_CATALOGUE = [
    ("first_crawl",         "🚀", "Первый парсинг",         "Запустите парсинг сайта впервые",           "crawler"),
    ("crawl_5",             "🔄", "5 запусков",             "Запустите парсинг 5 раз",                   "crawler"),
    ("crawl_20",            "🌠", "20 запусков",            "Запустите парсинг 20 раз",                  "crawler"),
    ("pages_10",            "📚", "10 страниц",             "Парсинг 10+ страниц за раз",                "crawler"),
    ("pages_50",            "📖", "50 страниц",             "Парсинг 50+ страниц за раз",                "crawler"),
    ("pages_200",           "🏆", "200 страниц",            "Парсинг 200 страниц за раз",                "crawler"),
    ("first_dialog",        "💬", "Первый диалог",          "Первый пользователь написал боту",          "dialogs"),
    ("dialogs_10",          "🗨️", "10 диалогов",            "Бот ответил на 10 сессий",                  "dialogs"),
    ("dialogs_50",          "📞", "50 диалогов",            "Бот ответил на 50 сессий",                  "dialogs"),
    ("dialogs_200",         "🏅", "200 диалогов",           "Бот ответил на 200 сессий",                 "dialogs"),
    ("messages_100",        "📨", "100 сообщений",          "Бот получил 100 сообщений",                 "dialogs"),
    ("messages_1000",       "📡", "1000 сообщений",         "Бот получил 1000 сообщений",                "dialogs"),
    ("first_operator",      "🧑‍💻", "Первое обращение",       "Первый запрос оператору",                 "operator"),
    ("operator_10",         "🎧", "10 обращений",           "Отвечено 10 запросов оператору",            "operator"),
    ("operator_50",         "🏄", "50 обращений",           "Отвечено 50 запросов",                      "operator"),
    ("settings_configured", "⚙️", "Настройка выполнена",    "Заполнены все настройки бота",              "settings"),
    ("daily_7",             "🗓️", "7 дней подряд",          "Выполняйте задачи 7 дней подряд",           "daily"),
    ("daily_30",            "📅", "30 дней подряд",         "Выполняйте задачи 30 дней подряд",          "daily"),
]
ACHIEVEMENT_MAP = {
    a[0]: {"emoji": a[1], "title": a[2], "description": a[3], "category": a[4]}
    for a in ACHIEVEMENT_CATALOGUE
}

DAILY_TASK_DEFS = [
    {"key": "check_dialogs", "title": "Просмотреть историю диалогов", "icon": "MessageSquare"},
    {"key": "check_crm",     "title": "Проверить заявки в CRM",       "icon": "ShoppingCart", "no_action": True},
]


class CompleteTaskRequest(BaseModel):
    task_key: str


def try_unlock(db: Session, key: str) -> bool:
    if db.query(Achievement).filter(Achievement.key == key).first():
        return False
    db.add(Achievement(key=key, unlocked_at=datetime.now(timezone.utc), is_new=True))
    db.commit()
    return True


def compute_streak(db: Session) -> int:
    rows = db.execute(text("""
        SELECT completed_date, COUNT(DISTINCT task_key) as cnt
        FROM daily_tasks
        GROUP BY completed_date
        HAVING cnt >= :total
        ORDER BY completed_date DESC
    """), {"total": len(DAILY_TASK_DEFS)}).fetchall()

    streak = 0
    check_date = date.today()
    date_set = {r[0] for r in rows}
    while check_date.strftime("%Y-%m-%d") in date_set:
        streak += 1
        check_date -= timedelta(days=1)
    return streak


async def check_achievements(db: Session) -> list[str]:
    stats = db.query(Stats).filter(Stats.id == 1).first()
    s = db.query(SettingsModel).first()

    crawl_runs = stats.total_crawl_runs if stats else 0
    max_pages  = stats.max_pages_in_run if stats else 0
    dialogs    = stats.total_dialog_sessions if stats else 0
    messages   = stats.total_user_messages if stats else 0
    op_req     = stats.total_operator_requested if stats else 0
    op_ans     = stats.total_operator_answered if stats else 0
    streak     = compute_streak(db)

    checks = [
        ("first_crawl",         crawl_runs >= 1),
        ("crawl_5",             crawl_runs >= 5),
        ("crawl_20",            crawl_runs >= 20),
        ("pages_10",            max_pages >= 10),
        ("pages_50",            max_pages >= 50),
        ("pages_200",           max_pages >= 200),
        ("first_dialog",        dialogs >= 1),
        ("dialogs_10",          dialogs >= 10),
        ("dialogs_50",          dialogs >= 50),
        ("dialogs_200",         dialogs >= 200),
        ("messages_100",        messages >= 100),
        ("messages_1000",       messages >= 1000),
        ("first_operator",      op_req >= 1),
        ("operator_10",         op_ans >= 10),
        ("operator_50",         op_ans >= 50),
        ("settings_configured", bool(s and s.openai_key and s.bot_name and s.target_url)),
        ("daily_7",             streak >= 7),
        ("daily_30",            streak >= 30),
    ]

    newly_unlocked = [key for key, cond in checks if cond and try_unlock(db, key)]
    
    if newly_unlocked:
        await sse_manager.broadcast("achievement_unlocked", None)


@router.get("")
async def get_gamification(db: Session = Depends(get_db)):
    await check_achievements(db)

    unlocked = db.query(Achievement).order_by(desc(Achievement.unlocked_at)).all()
    unlocked_keys = {a.key for a in unlocked}

    catalogue = []
    for key, meta in ACHIEVEMENT_MAP.items():
        a = next((x for x in unlocked if x.key == key), None)
        catalogue.append({
            "key": key,
            "emoji": meta["emoji"],
            "title": meta["title"],
            "description": meta["description"],
            "category": meta["category"],
            "unlocked": key in unlocked_keys,
            "unlockedAt": a.unlocked_at.isoformat() if a else None,
            "isNew": bool(a.is_new) if a else False,
        })

    today = datetime.now(timezone.utc).date().isoformat()
    completed_today = {
        r.task_key
        for r in db.query(DailyTask).filter(DailyTask.completed_date == today).all()
    }
    tasks = [{**t, "completed": t["key"] in completed_today} for t in DAILY_TASK_DEFS]
    new_count = sum(1 for a in unlocked if a.is_new)

    return {
        "achievements": catalogue,
        "tasks": tasks,
        "stats": {
            "total": len(catalogue),
            "unlocked": len(unlocked_keys),
            "newCount": new_count,
        },
    }


@router.post("/complete-task")
def complete_daily_task(req: CompleteTaskRequest, db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date().isoformat()
    exists = db.query(DailyTask).filter(
        DailyTask.task_key == req.task_key,
        DailyTask.completed_date == today,
    ).first()
    if not exists:
        db.add(DailyTask(
            task_key=req.task_key,
            completed_date=today,
            completed_at=datetime.now(timezone.utc),
        ))
        db.commit()
        streak = compute_streak(db)
        if streak >= 7:
            try_unlock(db, "daily_7")
        if streak >= 30:
            try_unlock(db, "daily_30")
    return {"ok": True}


@router.post("/mark-seen")
async def mark_achievements_seen(db: Session = Depends(get_db)):
    db.query(Achievement).filter(Achievement.is_new == True).update({"is_new": False})
    db.commit()
    await sse_manager.broadcast("achievement_unlocked", None)
    return {"ok": True}
