import logging
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin, urlunparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import or_
from sqlalchemy.orm import Session
import asyncio

from .models import Page, Chunk, CrawlSession, Settings
from .qdrant_store import upsert_chunk, clear_collection, init_collection, is_low_quality_chunk
from .sse_manager import sse_manager

logger = logging.getLogger(__name__)

MAX_PAGES = 200
MAX_QUEUE_SIZE = 60
REQUEST_TIMEOUT = 6
DELAY_BETWEEN_REQUESTS = 0.2

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

visited = set()

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

def parse_html(html: str, base_url: str, db: Session) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")

    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or any(href.startswith(p) for p in ("mailto:", "tel:", "javascript:", "#", "data:")):
            continue
        norm = normalize_url(href, base_url)
        if norm and norm not in seen and is_same_domain(norm, base_url) and not has_skip_extension(norm):
            seen.add(norm)
            links.append(norm)

    s = db.query(Settings).first()
    crawler_settings = s.crawler_settings if s else ""
    user_items = crawler_settings.split() if crawler_settings else []

    extra_tags = [x for x in user_items if not x.startswith('.') and not x.startswith('#')]
    css_selectors = [x for x in user_items if x.startswith('.') or x.startswith('#') or '[' in x or ' ' in x or '>' in x or ':' in x]

    if extra_tags:
        for t in soup.find_all(extra_tags):
            t.decompose()

    to_remove = []
    seen_tags = set()
    for selector in css_selectors:
        try:
            for t in soup.select(selector):
                key = id(t)
                if key not in seen_tags:
                    seen_tags.add(key)
                    to_remove.append(t)
        except Exception:
            continue

    for t in to_remove:
        t.decompose()

    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "Без заголовка"

    main = (
        soup.find("main") or
        soup.find(attrs={"role": "main"}) or
        soup.find("article") or
        soup.find(id=lambda x: x and "content" in x.lower()) or
        soup.find(attrs={"class": lambda c: c and "content" in " ".join(c).lower()}) or
        soup.body or
        soup
    )

    text = " ".join(main.get_text(separator=" ", strip=True).split())
    return title, text, links

def split_into_chunks(text: str, chunk_size: int = 800, overlap: int = 100):
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            boundary = max(
                text.rfind(". ", start, end),
                text.rfind("! ", start, end),
                text.rfind("? ", start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunks.append(text[start:end].strip())
        if end >= n:
            break

        new_start = max(0, end - overlap)
        next_sentence = max(
            text.find(". ", new_start),
            text.find("! ", new_start),
            text.find("? ", new_start),
        )
        if next_sentence != -1 and next_sentence < end:
            start = next_sentence + 2
        else:
            word_start = text.find(" ", new_start)
            start = word_start + 1 if word_start != -1 else new_start

    return chunks

def fetch_page(url: str) -> str | None:
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if not r.ok:
            return None
        ctype = r.headers.get("content-type", "").lower()
        if "text/html" not in ctype:
            return None
        r.encoding = r.encoding or "utf-8"
        return r.text
    except requests.exceptions.RequestException as e:
        logger.warning(f"Fetch error {url}: {e}")
        return None

def crawl_site(session_id: int, target_url: str, db: Session, loop=None) -> None:
    start_url = normalize_url(target_url, target_url) or target_url.strip()

    db.query(Chunk).delete()
    db.query(Page).delete()
    db.commit()

    try:
        clear_collection()
    except Exception as e:
        logger.warning(f"Qdrant clear failed: {e}")
        try:
            init_collection()
        except Exception as e2:
            logger.warning(f"Qdrant init failed: {e2}")

    visited.clear()
    to_visit = [start_url]
    queued = {start_url}
    pages_done = 0

    def update_progress():
        sess = db.get(CrawlSession, session_id)
        if sess:
            sess.pages_found = len(visited) + len(to_visit)
            sess.pages_done = pages_done
            db.merge(sess)
            db.commit()

        # broadcast прогресса через SSE
        try:
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    sse_manager.broadcast("crawl_progress", {
                        "status": "running",
                        "pagesDone": pages_done,
                        "pagesFound": len(visited) + len(to_visit),
                    }),
                    loop
                )
        except Exception:
            pass

    while to_visit and pages_done < MAX_PAGES:
        url = to_visit.pop(0)
        queued.discard(url)

        if url in visited:
            continue
        visited.add(url)

        logger.info(f"FETCH {url}")
        html = fetch_page(url)
        if not html:
            continue

        title, content, links = parse_html(html, url, db)
        logger.info(f"PARSE {url} links={len(links)} content={len(content)}")

        if len(content) < 50:
            continue

        for link in links:
            if link not in visited and link not in queued and len(to_visit) < MAX_QUEUE_SIZE:
                queued.add(link)
                to_visit.append(link)

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
            point_id = page_id * 10_000 + idx
            if is_low_quality_chunk(chunk_text):
                continue
            try:
                upsert_chunk(
                    chunk_id=point_id,
                    chunk_text=chunk_text,
                    page_url=url,
                    page_title=title[:500],
                )
            except Exception as e:
                logger.warning(f"Qdrant upsert failed (page_id={page_id}, idx={idx}): {e}")

        pages_done += 1
        logger.info(f"OK {pages_done}: {url}")
        update_progress()

        time.sleep(DELAY_BETWEEN_REQUESTS)

    crawl_session = db.get(CrawlSession, session_id)
    if crawl_session:
        crawl_session.status = "done"
        crawl_session.finished_at = datetime.now()
        crawl_session.pages_done = pages_done
        crawl_session.pages_found = len(visited)
        db.commit()

    logger.info(f"Crawl done: {pages_done} pages from {target_url}")

def search_chunks(db: Session, query: str, limit: int = 5):
    words = [w for w in query.lower().split() if len(w) > 2]
    if not words:
        return []

    conditions = [Chunk.chunk_text.ilike(f"%{w}%") for w in words]
    candidates = (
        db.query(Chunk)
        .filter(or_(*conditions))
        .limit(200)
        .all()
    )

    scored = []
    for chunk in candidates:
        text_lower = chunk.chunk_text.lower()
        score = sum(text_lower.count(w) for w in words)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]
