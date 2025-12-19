import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env (если файл есть рядом с проектом)
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)

# === Основные настройки ===

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# База данных
DB_PATH = os.getenv("DB_PATH", "beauty_data.db")

# Парсер
MAX_PAGES = int(os.getenv("MAX_PAGES", "30"))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (beauty-bot)")

# Flask
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"


def validate_config():
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if missing:
        raise RuntimeError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}")
