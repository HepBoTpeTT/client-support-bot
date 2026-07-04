from math import isclose

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

from config import settings

COLLECTION_NAME = "site_chunks"

_client: QdrantClient | None = None
_model: TextEmbedding | None = None


def get_qdrant() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
    return _client


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(settings.embedding_model, cache_dir="/model_cache")
    return _model


def embed_passage(text: str) -> list[float]:
    return list(get_model().embed([f"passage: {text}"]))[0].tolist()


def embed_query(text: str) -> list[float]:
    return list(get_model().embed([f"query: {text}"]))[0].tolist()


def init_collection() -> None:
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        vector_size = len(embed_passage("test"))
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )


def clear_collection() -> None:
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
    init_collection()


def is_low_quality_chunk(text: str) -> bool:
    text = (text or "").strip()
    if len(text) < 50:
        return True
    words = text.split()
    if not words:
        return True
    unique_ratio = len(set(words)) / len(words)
    if unique_ratio < 0.4 and len(words) > 30:
        return True
    return False


def upsert_chunk(chunk_id: int, chunk_text: str, page_url: str, page_title: str) -> None:
    vector = embed_passage(chunk_text)

    get_qdrant().upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "chunk_text": chunk_text,
                    "page_url": page_url,
                    "page_title": page_title,
                },
            )
        ],
    )


def search_similar(query: str, limit: int = 5, score_threshold: float = 0.35) -> list[dict]:
    vector = embed_query(query)
    fetch_limit = max(limit * 5, limit + 20)

    results = get_qdrant().search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=fetch_limit,
        score_threshold=score_threshold,
    )

    filtered = []
    seen_texts = set()

    for r in results:
        payload = r.payload or {}
        chunk_text = payload.get("chunk_text", "")
        if not chunk_text:
            continue
        if r.score < score_threshold:
            continue

        text_key = chunk_text[:100]
        if text_key in seen_texts:
            continue

        seen_texts.add(text_key)
        filtered.append(r)

    if not filtered:
        return []

    filtered.sort(key=lambda r: r.score, reverse=True)

    if len(filtered) <= limit:
        kept = filtered
    else:
        cutoff_score = filtered[limit - 1].score
        kept = []
        for r in filtered:
            if len(kept) < limit:
                kept.append(r)
                continue
            if isclose(r.score, cutoff_score, rel_tol=1e-9, abs_tol=1e-9):
                kept.append(r)
            else:
                break

    return [
        {
            "chunk_text": r.payload["chunk_text"],
            "page_url": r.payload["page_url"],
            "page_title": r.payload.get("page_title", ""),
            "score": r.score,
        }
        for r in kept
    ]
