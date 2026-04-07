from qdrant_client import QdrantClient, models
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


def init_collection() -> None:
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        # Определяем размерность динамически из модели
        vector_size = len(list(get_model().embed(["test"]))[0].tolist())
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
    text = text.strip()
    if len(text) < 50:
        return True
    words = text.split()
    unique_ratio = len(set(words)) / len(words)
    if unique_ratio < 0.4 and len(words) > 30:
        return True
    return False


def upsert_chunk(chunk_id: int, chunk_text: str, page_url: str, page_title: str) -> None:
    model = get_model()
    vector = list(model.embed([chunk_text]))[0].tolist()

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
    vector = list(get_model().embed([query]))[0].tolist()

    results = get_qdrant().search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=limit,
        score_threshold=score_threshold,
    )
    for r in results:
        print(f"Score: {r.score:.3f} | {r.payload['page_url']}")

    seen_texts = set()
    unique_results = []
    for r in results:
        text_key = r.payload["chunk_text"][:100]
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            unique_results.append(r)
    results = unique_results

    max_score = max((r.score for r in results), default=0)

    if max_score < 0.5:
        keywords = [w for w in query.lower().split() if len(w) > 3]
        extra_points, _ = get_qdrant().scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                should=[
                    models.FieldCondition(
                        key="chunk_text",
                        match=models.MatchText(text=kw)
                    )
                    for kw in keywords
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        existing_ids = {r.id for r in results}
        for p in extra_points:
            if p.id not in existing_ids:
                # Оборачиваем в тот же формат что возвращает search()
                results.append(type("R", (), {
                    "id": p.id,
                    "score": 0.0,
                    "payload": p.payload
                })())

    return [
        {
            "chunk_text": r.payload["chunk_text"],
            "page_url": r.payload["page_url"],
            "page_title": r.payload.get("page_title", ""),
            "score": r.score,
        }
        for r in results
    ]
