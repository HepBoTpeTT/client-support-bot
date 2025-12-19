import logging
import config

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from universal_parser import scrape_recursive, save_to_db, init_db
from semantic import embed_pages, search_similar
from openai_helper import ask_gpt


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бьюти-бот 💄\n\n"
        "🔄 Используй команду /parse <ссылка>, чтобы загрузить сайт.\n"
        "🤔 После этого просто задай вопрос."
    )

# === Команда /parse ===
async def parse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text(
            "Пожалуйста, укажи ссылку:\n"
            "/parse https://example.com"
        )
        return

    url = context.args[0]

    try:
        await update.message.reply_text(f"⏳ Паршу сайт (до {config.MAX_PAGES} страниц): {url}")

        pages = scrape_recursive(url, max_pages=config.MAX_PAGES)
        if not pages:
            await update.message.reply_text("❌ Не удалось получить содержимое страниц. Проверь ссылку.")
            return

        save_to_db(pages)
        embed_pages()

        await update.message.reply_text(
            f"✅ Успешно спарсено {len(pages)} страниц и обновлены эмбеддинги."
        )
    except Exception as e:
        logger.exception("Ошибка при парсинге")
        await update.message.reply_text(f"❌ Ошибка при парсинге: {e}")


# === Обработка текстовых сообщений (вопросов) ===
async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text

    try:
        results = search_similar(question)
        if not results:
            await update.message.reply_text(
                "❌ Ничего не найдено.\n"
                "Сначала спарси сайт командой /parse <ссылка>."
            )
            return

        context_blocks = [(url, content[:1000]) for _, url, content in results]
        answer = ask_gpt(context_blocks, question)

        await update.message.reply_text(answer)
    except Exception as e:
        logger.exception("Ошибка при ответе на вопрос")
        await update.message.reply_text(f"❌ Ошибка: {e}")

# === Основной запуск бота ===
if __name__ == '__main__':
    # Проверяем конфиг и инициализируем БД
    config.validate_config()
    init_db()

    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("parse", parse))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer_question))

    print("🚀 Бот запущен")
    app.run_polling()
