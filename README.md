# Site Assistant — AI-виджет помощника

**Стек:** Python 3.11+ / FastAPI / SQLAlchemy / MySQL · React 18 / TypeScript / Vite / shadcn-ui

---

## Структура проекта

```
site-assistant-py/
├── backend/               ← FastAPI-приложение (Python)
│   ├── main.py            ← точка входа, все API-маршруты
│   ├── crawler.py         ← парсер сайта (httpx + BeautifulSoup)
│   ├── qdrant_store.py    ← векторное хранилище (Qdrant + fastembed)
│   ├── models.py          ← SQLAlchemy-модели (MySQL)
│   ├── database.py        ← подключение к БД, init_db()
│   ├── config.py          ← настройки через .env (pydantic-settings)
│   ├── widget.py          ← генератор widget.js и iframe-HTML
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
├── frontend/              ← React + TypeScript (Vite)
│   ├── src/
│   │   ├── pages/         ← CrawlerPage, PagesPage, DialogsPage, SettingsPage, EmbedPage
│   │   └── components/
│   └── package.json
```

---

## Требования

- **Docker** и **Docker Compose**
- **OpenAI API ключ**
- Для запуска из России — локальный прокси (v2ray/xray или аналог)

---

## Быстрый старт (Docker Compose)

1. Клонировать репозиторий
2. Создать .env в папке *backend/*, внутри имеется файл .env.example.
3. Запустить `cd backend docker compose up -d --build `

Таблицы создаются **автоматически** при первом запуске.

---

## Первая настройка

1. Открыть http://localhost:5173
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
