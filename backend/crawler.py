import gc
import logging
import time
from collections import deque
from urllib.parse import urlparse, urljoin, urlunparse
from bs4 import BeautifulSoup
import httpx
from sqlalchemy.orm import Session
from models import Page, Chunk, CrawlSession
from datetime import datetime
from qdrant_store import clear_collection, upsert_chunk, search_similar

logger = logging.getLogger(__name__)

MAX_PAGES = 200
MAX_QUEUE_SIZE = 60
MAX_HTML_SIZE = 200_000
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
REQUEST_TIMEOUT = 15.0
DELAY_BETWEEN_REQUESTS = 0.3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".zip", ".rar", ".exe", ".dmg", ".mp4", ".mp3", ".avi",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".css", ".js", ".json", ".xml", ".ico", ".woff", ".woff2", ".ttf",
}


def normalize_url(url: str, base: str) -> str | None:
    try:
        parsed = urlparse(urljoin(base, url))
        if parsed.scheme not in ("http", "https"):
            return None
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        clean = parsed._replace(netloc=netloc, fragment="", query="")
        result = urlunparse(clean)
        if result.endswith("/") and parsed.path not in ("", "/"):
            result = result.rstrip("/")
        return result
    except Exception:
        return None


def is_same_domain(url: str, base: str) -> bool:
    try:
        u = urlparse(url)
        b = urlparse(base)
        return u.netloc.lower().lstrip("www.") == b.netloc.lower().lstrip("www.")
    except Exception:
        return False


def has_skip_extension(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


def parse_html(html: str, base_url: str) -> tuple[str, str, list[str]]:
    """Один проход BeautifulSoup — возвращает (title, text, links)."""
    soup = BeautifulSoup(html, "html.parser")

    # Ссылки — до удаления тегов
    links = []
    seen = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or any(href.startswith(p) for p in ("mailto:", "tel:", "javascript:", "#", "data:")):
            continue
        norm = normalize_url(href, base_url)
        if norm and norm not in seen and is_same_domain(norm, base_url) and not has_skip_extension(norm):
            seen.add(norm)
            links.append(norm)

    # Удаляем шумовые теги
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    # Заголовок
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "Без заголовка"

    # Текст
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body
    text = " ".join((main or soup).get_text(separator=" ").split())

    soup.clear()
    del soup

    return title, text, links


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 3)
    n = len(text)
    if n <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


def fetch_page(client: httpx.Client, url: str) -> str | None:
    try:
        with client.stream("GET", url, headers=HEADERS, timeout=REQUEST_TIMEOUT) as response:
            if not response.is_success:
                return None
            if "text/html" not in response.headers.get("content-type", ""):
                return None
            chunks_raw = []
            size = 0
            for chunk in response.iter_bytes(chunk_size=16384):
                size += len(chunk)
                if size > MAX_HTML_SIZE:
                    break
                chunks_raw.append(chunk)
            html = b"".join(chunks_raw).decode("utf-8", errors="replace")
            del chunks_raw
            return html
    except Exception as e:
        logger.warning(f"Fetch error {url}: {e}")
        return None


def crawl_site(session_id: int, target_url: str, db: Session) -> None:
    start_url = normalize_url(target_url, target_url) or target_url

    # Pre-flight
    try:
        with httpx.Client(verify=False, follow_redirects=True, timeout=15) as probe:
            r = probe.get(start_url, headers=HEADERS)
            if not r.is_success:
                raise Exception(f"Сайт вернул статус {r.status_code}. Проверьте URL.")
    except httpx.ConnectError:
        raise Exception(f"Не удаётся подключиться к {target_url}. Проверьте URL.")
    except httpx.TimeoutException:
        raise Exception(f"Сайт {target_url} не отвечает (таймаут).")

    # Очищаем старые данные
    db.query(Chunk).delete()
    db.query(Page).delete()
    db.commit()
    clear_collection()

    visited: set[str] = set()
    queued: set[str] = {start_url}
    queue: deque[str] = deque([start_url])
    pages_done = 0

    def update_progress():
        sess = db.get(CrawlSession, session_id)
        if sess:
            sess.pages_found = len(visited) + len(queue)
            sess.pages_done = pages_done
            db.commit()

    with httpx.Client(verify=False, follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        while queue and pages_done < MAX_PAGES:
            url = queue.popleft()
            queued.discard(url)

            if url in visited:
                continue
            visited.add(url)

            # logger.info(f"Парсим: {url}")

            html = fetch_page(client, url)
            if not html:
                continue

            title, content, links = parse_html(html, url)
            del html

            if len(content) < 50:
                del content, links
                continue

            # Добавляем ссылки в очередь
            if len(queue) < MAX_QUEUE_SIZE:
                for link in links:
                    if link not in visited and link not in queued:
                        if len(queue) >= MAX_QUEUE_SIZE:
                            break
                        queued.add(link)
                        queue.append(link)

            del links

            # Сохраняем в БД
            page = Page(url=url, title=title[:500], content=content, status="done", crawled_at=datetime.now())
            db.add(page)
            db.flush()
            page_id = page.id

            chunks = split_into_chunks(content)
            for idx, chunk_text in enumerate(chunks):
                db.add(Chunk(
                    page_id=page_id,
                    page_url=url,
                    page_title=title[:500],
                    chunk_text=chunk_text,
                    chunk_index=idx,
                ))

            db.commit()
            db.expunge_all()

            for idx, chunk_text in enumerate(chunks):
                # простая схема уникальных ID: page_id * 10_000 + idx
                point_id = page_id * 10_000 + idx
                upsert_chunk(
                    chunk_id=point_id,
                    chunk_text=chunk_text,
                    page_url=url,
                    page_title=title[:500],
                )

            del content, title, chunks
            gc.collect()

            pages_done += 1
            logger.info(f"  → страница #{pages_done} сохранена: {url}")
            if pages_done % 5 == 0 or pages_done == 1:
                update_progress()

            time.sleep(DELAY_BETWEEN_REQUESTS)

    # Финализируем
    crawl_session = db.get(CrawlSession, session_id)
    if crawl_session:
        crawl_session.status = "done"
        crawl_session.finished_at = datetime.now()
        crawl_session.pages_done = pages_done
        crawl_session.pages_found = len(visited)  # сколько всего было обнаружено/посещено
        db.commit()

    logger.info(f"Crawl done: {pages_done} pages from {target_url}")


def search_chunks(query: str, limit: int = 5) -> list[dict]:
    return search_similar(query, limit=limit)
