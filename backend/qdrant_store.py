from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding
from config import settings

COLLECTION_NAME = "site_chunks"
VECTOR_SIZE = 384  # для all-MiniLM-L6-v2

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
        _model = TextEmbedding("BAAI/bge-small-en-v1.5", cache_dir="/app/model_cache")
    return _model


def init_collection() -> None:
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )


def clear_collection() -> None:
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
    init_collection()


def upsert_chunk(chunk_id: int, chunk_text: str, page_url: str, page_title: str) -> None:
    model = get_model()
    vector = list(get_model().embed([chunk_text]))[0].tolist()

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


def search_similar(query: str, limit: int = 5) -> list[dict]:
    vector = list(get_model().embed([query]))[0].tolist()

    results = get_qdrant().search(
        collection_name=COLLECTION_NAME,
        query_vector=vector,
        limit=limit,
    )

    return [
        {
            "chunk_text": r.payload["chunk_text"],
            "page_url": r.payload["page_url"],
            "page_title": r.payload.get("page_title", ""),
            "score": r.score,
        }
        for r in results
    ]
