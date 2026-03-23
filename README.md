# Site Assistant — AI-виджет помощника

**Стек:** Python 3.11 / FastAPI / SQLAlchemy / MySQL · React 18 / TypeScript / Vite / shadcn-ui · Qdrant · fastembed (BAAI/bge-small-en-v1.5)

---

## Структура проекта

site-assistant-py/
├── backend/ ← FastAPI-приложение (Python)
│ ├── main.py ← точка входа, все API-маршруты
│ ├── crawler.py ← парсер сайта (httpx + BeautifulSoup)
│ ├── qdrant_store.py ← векторное хранилище (Qdrant + fastembed)
│ ├── models.py ← SQLAlchemy-модели (MySQL)
│ ├── database.py ← подключение к БД, init_db()
│ ├── config.py ← настройки через .env (pydantic-settings)
│ ├── widget.py ← генератор widget.js и iframe-HTML
│ ├── Dockerfile
│ └── requirements.txt
├── frontend/ ← React + TypeScript (Vite)
│ ├── src/
│ │ ├── pages/ ← CrawlerPage, PagesPage, DialogsPage, SettingsPage, EmbedPage
│ │ └── components/
│ └── package.json
└── docker-compose.yml

text

---

## Требования

- **Docker** и **Docker Compose**
- **OpenAI API ключ**
- Для запуска из России — локальный прокси (v2ray/xray или аналог) на `127.0.0.1:10808`

---

## Быстрый старт (Docker Compose)

### 1. Клонировать репозиторий

```bash
git clone https://github.com/your-repo/site-assistant-py.git
cd site-assistant-py
2. Создать .env в папке backend/
text
# MySQL
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=ВАШ_ПАРОЛЬ
MYSQL_DATABASE=site_assistant

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Прокси для OpenAI (если запуск из России)
# Укажи адрес локального прокси на хост-машине
HTTPS_PROXY=http://host.docker.internal:10808
3. Запустить
bash
docker compose up -d --build
Поднимутся 4 контейнера:

Контейнер	Описание	Порт
mysql	База данных	3306
qdrant	Векторное хранилище	6333
backend	FastAPI	8000
frontend	React (Vite)	5173
4. Открыть панель управления
text
http://localhost:5173
Первая настройка
Настройки → вставить OpenAI API ключ (sk-...), задать имя бота и язык

Парсинг сайта → ввести URL → нажать «Запустить»

Дождаться завершения — страницы и чанки сохранятся в MySQL и Qdrant

Код встраивания → скопировать JS-сниппет или iFrame

Как работает RAG
text
Вопрос пользователя
       ↓
Векторизация (fastembed BAAI/bge-small-en-v1.5, локально)
       ↓
Поиск top-5 чанков в Qdrant (cosine similarity, 384 dim)
       ↓
Чанки вставляются в system prompt OpenAI
       ↓
Ответ GPT на основе контента сайта
Модель fastembed скачивается при сборке образа и хранится в /app/model_cache — интернет при каждом запросе не нужен.

Проверка Qdrant
Веб-интерфейс: http://localhost:6333/dashboard

API: http://localhost:6333/collections

Встраивание на сторонний сайт
Вариант 1 — JavaScript (рекомендуется)
xml
<!-- Вставить перед </body> -->
<script>
(function(){
  var s=document.createElement('script');
  s.src='http://ВАШ_СЕРВЕР:8000/widget.js';
  document.head.appendChild(s);
})();
</script>
Вариант 2 — iFrame
xml
<iframe
  src="http://ВАШ_СЕРВЕР:8000/chat-widget"
  style="position:fixed;bottom:20px;right:20px;width:400px;height:600px;border:none;z-index:9999;border-radius:16px;"
></iframe>
API (Swagger)
Документация: http://localhost:8000/docs

Метод	Путь	Описание
Метод	Путь	Описание
GET	/api/settings	Получить настройки
PATCH	/api/settings	Обновить настройки
POST	/api/crawl/start	Запустить парсинг {"url":"https://..."}
GET	/api/crawl/status	Статус последнего парсинга
GET	/api/pages	Список спарсированных страниц
DELETE	/api/pages	Очистить базу знаний
POST	/api/chat	Чат {"message":"...","session_id":"..."}
GET	/api/dialogs	Список сессий диалогов
GET	/api/dialogs/{session_id}	Сообщения сессии
GET	/api/embed-code	Сниппеты для встраивания
text

Скопируй целиком и сохрани как `README.md` в корне проекта.