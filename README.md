# Site Assistant — AI-виджет помощника

**Стек:** Python 3.11+ / FastAPI / SQLAlchemy / MySQL · React 18 / TypeScript / Vite / shadcn-ui

---

## Структура проекта

```
site-assistant-py/
├── backend/          ← FastAPI-приложение (Python)
│   ├── main.py       ← точка входа, все API-маршруты
│   ├── crawler.py    ← парсер сайта (httpx + BeautifulSoup)
│   ├── models.py     ← SQLAlchemy-модели (MySQL)
│   ├── database.py   ← подключение к БД, init_db()
│   ├── config.py     ← настройки через .env (pydantic-settings)
│   ├── widget.py     ← генератор widget.js и iframe-HTML
│   ├── requirements.txt
│   └── .env.example
└── frontend/         ← React + TypeScript (Vite)
    ├── client/src/
    │   ├── pages/    ← CrawlerPage, PagesPage, DialogsPage, SettingsPage, EmbedPage
    │   └── components/
    └── package.json
```

---

## Требования

- **Python 3.11+**
- **Node.js 18+** и **npm**
- **MySQL 8+** (или MariaDB 10.6+)
- **OpenAI API ключ**

---

## Шаг 1 — Создать базу данных MySQL

```sql
CREATE DATABASE site_assistant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Опционально: создать отдельного пользователя
CREATE USER 'assistant'@'localhost' IDENTIFIED BY 'StrongPassword123';
GRANT ALL PRIVILEGES ON site_assistant.* TO 'assistant'@'localhost';
FLUSH PRIVILEGES;
```

---

## Шаг 2 — Настроить бэкенд

```bash
cd backend

# Создать виртуальное окружение
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/macOS

# Установить зависимости
pip install -r requirements.txt

# Создать .env из шаблона
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/macOS

# Открыть .env и заполнить MYSQL_PASSWORD и другие параметры
```

Содержимое `.env`:
```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=ВАШ_ПАРОЛЬ
MYSQL_DATABASE=site_assistant
PORT=8000
```

Запустить бэкенд:
```bash
python main.py
# API доступен на http://localhost:8000
# Swagger-документация: http://localhost:8000/docs
```

Таблицы создаются **автоматически** при первом запуске.

---

## Шаг 3 — Запустить фронтенд (режим разработки)

```bash
cd frontend
npm install
npm run dev
# Открыть http://localhost:5173
```

Vite автоматически проксирует все `/api/*` запросы на FastAPI (порт 8000).

---

## Продакшн (фронтенд встроен в бэкенд)

```bash
# Собрать фронтенд
cd frontend
npm run build
# Артефакты окажутся в frontend/dist/

# Запустить только Python-сервер
cd ../backend
python main.py
# Открыть http://localhost:8000 — подаёт и API, и фронтенд
```

---

## Первая настройка

1. Открыть http://localhost:8000 (или :5173 в dev-режиме)
2. **Настройки виджета** → вставить OpenAI API ключ (sk-...)
3. **Парсинг сайта** → ввести URL сайта → нажать «Запустить»
4. Дождаться завершения (раздел «База знаний» заполнится страницами)
5. **Код встраивания** → скопировать JS-сниппет или iFrame

---

## Встраивание на сторонний сайт

### Вариант 1 — JavaScript (рекомендуется)
```html
<!-- Вставить перед </body> -->
<script>
(function(){
  var s=document.createElement('script');
  s.src='http://ВАШ_СЕРВЕР:8000/widget.js';
  document.head.appendChild(s);
})();
</script>
```

### Вариант 2 — iFrame
```html
<iframe
  src="http://ВАШ_СЕРВЕР:8000/chat-widget"
  style="position:fixed;bottom:20px;right:20px;width:400px;height:600px;border:none;z-index:9999;border-radius:16px;"
></iframe>
```

---

## API (Swagger)

Документация доступна на `http://localhost:8000/docs` после запуска сервера.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/settings` | Получить настройки |
| PATCH | `/api/settings` | Обновить настройки |
| POST | `/api/crawl/start` | Запустить парсинг `{"url":"https://..."}` |
| GET | `/api/crawl/status` | Статус последнего парсинга |
| GET | `/api/pages` | Список спарсированных страниц |
| DELETE | `/api/pages` | Очистить базу знаний |
| POST | `/api/chat` | Чат `{"message":"...","session_id":"..."}` |
| GET | `/api/dialogs` | Список сессий диалогов |
| GET | `/api/dialogs/{session_id}` | Сообщения сессии |
| GET | `/api/embed-code` | Сниппеты для встраивания |
