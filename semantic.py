import sqlite3
import numpy as np
import config
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_pages(batch_size: int = 32):
    """Вычисляет эмбеддинги для тех страниц, у которых embedding ещё не заполнен."""
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()

    # Берём только те записи, у которых embedding ещё NULL
    c.execute("SELECT id, content FROM pages WHERE embedding IS NULL")
    rows = c.fetchall()

    if not rows:
        conn.close()
        return

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]

        embs = model.encode(texts).astype(np.float32)

        for page_id, emb in zip(ids, embs):
            c.execute(
                "UPDATE pages SET embedding = ? WHERE id = ?",
                (emb.tobytes(), page_id),
            )

    conn.commit()
    conn.close()

def search_similar(question: str, top_n: int = 5, min_score: float = 0.3):
    """Ищет самые похожие страницы по косинусному сходству."""
    q_emb = model.encode(question)
    q_norm = np.linalg.norm(q_emb)
    if q_norm == 0:
        return []

    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT url, content, embedding FROM pages WHERE embedding IS NOT NULL")
    all_rows = c.fetchall()
    conn.close()

    results = []

    for url, content, emb in all_rows:
        emb_array = np.frombuffer(emb, dtype=np.float32)
        denom = np.linalg.norm(emb_array)
        if denom == 0:
            continue

        score = np.dot(q_emb, emb_array) / (q_norm * denom)
        if score >= min_score:
            results.append((score, url, content))

    results.sort(key=lambda x: x[0], reverse=True)
    return results[:top_n]
