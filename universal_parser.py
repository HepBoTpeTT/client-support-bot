import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sqlite3
import config


def init_db(db_path: str = "beauty_data.db"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        content TEXT,
        embedding BLOB
    )
    """)
    conn.commit()
    conn.close()

def is_valid_link(base_url, link):
    if not link or link.startswith('#') or link.startswith('mailto:') or link.startswith('tel:'):
        return False

    full_url = urljoin(base_url, link)
    return urlparse(full_url).netloc == urlparse(base_url).netloc

def extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(['script', 'style', 'noscript']):
        tag.extract()
    return ' '.join(soup.stripped_strings)

def scrape_recursive(base_url, max_pages=config.MAX_PAGES, db_path: str = config.DB_PATH):
    visited = set()
    to_visit = [base_url]
    content_blocks = []

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)

        if url in visited:
            continue

        try:
            print(f'📄 Парсим: {url}')
            response = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": config.USER_AGENT},
            )
            response.encoding = response.encoding or 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')
            text = extract_text(soup)

            if len(text) > 100:  # простая фильтрация мусора
                content_blocks.append((url, text.strip()))

                # ищем ссылки только если страница что-то дала
                for a in soup.find_all('a', href=True):
                    full_url = urljoin(url, a['href'])
                    if is_valid_link(base_url, a['href']) and full_url not in visited:
                        to_visit.append(full_url)

            visited.add(url)

        except Exception as e:
            print(f'❌ Ошибка на {url}: {e}')

    return content_blocks

def save_to_db(pages, db_path: str = "beauty_data.db"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        content TEXT,
        embedding BLOB
    )
    """)
    c.executemany('INSERT INTO pages (url, content) VALUES (?, ?)', pages)
    conn.commit()
    conn.close()
