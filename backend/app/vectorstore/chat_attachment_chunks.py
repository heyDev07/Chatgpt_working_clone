"""Conversation-scoped RAG for documents attached directly to a chat message - a separate
collection from document_chunks (the Knowledge Base), mirroring semantic_cache.py's precedent of
a dedicated collection rather than overloading an existing one: different lifecycle (tied to a
conversation's lifetime - deleted when the conversation is, see delete_conversation_chunks) and a
different scope key (conversation_id, not user_id - retrievable from anywhere in that one
conversation, never from another, and never listed in the user's Knowledge Base).
"""

import uuid

from qdrant_client import models

from app.config.settings import get_settings
from app.vectorstore.qdrant_client import get_qdrant_client

COLLECTION_NAME = "chat_attachment_chunks"
_NAMESPACE = uuid.UUID("2b6f8e1a-4c7d-4a3b-9e5f-7d1c8a2b6f9e")


async def ensure_collection() -> None:
    settings = get_settings()
    client = get_qdrant_client()
    if not await client.collection_exists(COLLECTION_NAME):
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=settings.embedding_dimensions, distance=models.Distance.COSINE),
        )


def _chunk_point_id(attachment_id: uuid.UUID, chunk_index: int) -> str:
    # Deterministic, same reasoning as qdrant_client.py's document chunks - re-processing the
    # same attachment (shouldn't normally happen, but harmless if it does) overwrites rather than
    # accumulating duplicates.
    return str(uuid.uuid5(_NAMESPACE, f"{attachment_id}:{chunk_index}"))


async def upsert_chunks(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    filename: str,
    chunks: list[str],
    vectors: list[list[float]],
) -> None:
    if not chunks:
        return
    client = get_qdrant_client()
    points = [
        models.PointStruct(
            id=_chunk_point_id(attachment_id, index),
            vector=vector,
            payload={
                "conversation_id": str(conversation_id),
                "attachment_id": str(attachment_id),
                "filename": filename,
                "chunk_index": index,
                "text": chunk,
            },
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    await client.upsert(collection_name=COLLECTION_NAME, points=points)


async def search(conversation_id: uuid.UUID, query_vector: list[float], limit: int = 5) -> list[tuple[dict, float]]:
    client = get_qdrant_client()
    response = await client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="conversation_id", match=models.MatchValue(value=str(conversation_id)))]
        ),
        limit=limit,
        with_payload=True,
    )
    return [(point.payload or {}, point.score) for point in response.points]


async def delete_conversation_chunks(conversation_id: uuid.UUID) -> None:
    client = get_qdrant_client()
    await client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="conversation_id", match=models.MatchValue(value=str(conversation_id))
                    )
                ]
            )
        ),
    )
