"""Semantic response cache: reuses the same embedding provider + Qdrant server already wired up
for document RAG (see qdrant_client.py) to skip a full LLM call when a new question is a near-
duplicate of one this user already asked. A separate collection from document_chunks - different
payload shape (question/answer pairs, not document excerpts) and a different lifecycle (TTL'd by
age, not tied to a document's existence) - so it mirrors the same ensure_collection()-at-startup
pattern rather than overloading one collection for two purposes. Scoped per-user (like
document_chunks) so one user's cached answers are never served to another.
"""

import time
import uuid
from functools import lru_cache

from qdrant_client import models

from app.config.settings import get_settings
from app.vectorstore.qdrant_client import get_qdrant_client

COLLECTION_NAME = "semantic_cache"
_NAMESPACE = uuid.UUID("8f1a2c6e-9d4b-4a7f-b3e1-5c6d8a9f0b12")

# Cosine similarity above which a cached answer is treated as a genuine near-duplicate rather than
# a coincidentally-similar-but-different question. Measured live against this project's actual
# embedding model (gemini-embedding-001), not guessed: "What is the capital of France?" vs a
# genuine rephrasing ("what is the capital city of France?") scores 0.91, while the dangerous
# near-miss case - same template, different fact, e.g. swapping in "Germany" - scores only 0.73.
# 0.90 sits just under the real paraphrase and well clear of the same-template/different-answer
# trap, which an earlier, unvalidated guess of 0.97 was too strict to ever match at all. A wrong
# cache hit (serving the wrong country's capital with total confidence) is a much worse
# user-visible failure than a miss, which just costs one ordinary LLM call - so when in doubt this
# stays on the stricter side of the measured gap, not the looser one.
SIMILARITY_THRESHOLD = 0.90

# Cached answers older than this are skipped even on a similarity match. Nothing here knows
# whether a given answer depended on time-sensitive facts, so this bounds how long a stale answer
# can keep being served rather than trying to classify staleness per-question.
TTL_SECONDS = 6 * 60 * 60


@lru_cache
def _cache_client():
    # Deliberately reuses get_qdrant_client()'s single AsyncQdrantClient instance rather than
    # opening a second connection to the same Qdrant server - this lru_cache only memoizes the
    # (trivial) indirection, not a distinct client.
    return get_qdrant_client()


async def ensure_cache_collection() -> None:
    settings = get_settings()
    client = _cache_client()
    if not await client.collection_exists(COLLECTION_NAME):
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=settings.embedding_dimensions, distance=models.Distance.COSINE),
        )


def _entry_point_id(user_id: uuid.UUID, question: str) -> str:
    # Deterministic on (user, normalized question) so asking the exact same thing again overwrites
    # the existing entry (refreshing its created_at/answer) instead of accumulating duplicates.
    return str(uuid.uuid5(_NAMESPACE, f"{user_id}:{question.strip().lower()}"))


async def find_cached_answer(user_id: uuid.UUID, query_vector: list[float]) -> str | None:
    client = _cache_client()
    response = await client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))]),
        limit=1,
        with_payload=True,
    )
    if not response.points:
        return None
    point = response.points[0]
    if point.score < SIMILARITY_THRESHOLD:
        return None
    payload = point.payload or {}
    if time.time() - payload.get("created_at", 0) > TTL_SECONDS:
        return None
    answer = payload.get("answer")
    return answer if isinstance(answer, str) and answer else None


async def store_cache_entry(user_id: uuid.UUID, question: str, answer: str, query_vector: list[float]) -> None:
    client = _cache_client()
    await client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=_entry_point_id(user_id, question),
                vector=query_vector,
                payload={
                    "user_id": str(user_id),
                    "question": question,
                    "answer": answer,
                    "created_at": time.time(),
                },
            )
        ],
    )
