import uuid
from functools import lru_cache

from qdrant_client import AsyncQdrantClient, models

from app.config.settings import get_settings

COLLECTION_NAME = "document_chunks"
_NAMESPACE = uuid.UUID("6d3f5b8a-4b2b-4c1a-9e2d-2f9b6a7c3d10")


@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(url=settings.qdrant_url)


async def ensure_collection() -> None:
    settings = get_settings()
    client = get_qdrant_client()
    if not await client.collection_exists(COLLECTION_NAME):
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=settings.embedding_dimensions, distance=models.Distance.COSINE
            ),
        )


def _chunk_point_id(document_id: uuid.UUID, chunk_index: int) -> str:
    # Deterministic id so re-processing the same document overwrites its old chunks
    # instead of accumulating duplicates.
    return str(uuid.uuid5(_NAMESPACE, f"{document_id}:{chunk_index}"))


async def upsert_chunks(
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    filename: str,
    chunks: list[str],
    vectors: list[list[float]],
) -> None:
    if not chunks:
        return
    client = get_qdrant_client()
    points = [
        models.PointStruct(
            id=_chunk_point_id(document_id, index),
            vector=vector,
            payload={
                "user_id": str(user_id),
                "document_id": str(document_id),
                "filename": filename,
                "chunk_index": index,
                "text": chunk,
            },
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    await client.upsert(collection_name=COLLECTION_NAME, points=points)


async def search(
    user_id: uuid.UUID,
    query_vector: list[float],
    limit: int = 5,
    document_id: uuid.UUID | None = None,
) -> list[tuple[dict, float]]:
    client = get_qdrant_client()
    must = [models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))]
    if document_id is not None:
        must.append(
            models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document_id)))
        )
    response = await client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=models.Filter(must=must),
        limit=limit,
        with_payload=True,
    )
    return [(point.payload or {}, point.score) for point in response.points]


async def delete_document_chunks(document_id: uuid.UUID) -> None:
    client = get_qdrant_client()
    await client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document_id)))]
            )
        ),
    )
