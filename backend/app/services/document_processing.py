import logging
import uuid

from app.config.settings import get_settings
from app.db.database import async_session_factory
from app.providers.provider_manager import ProviderManager
from app.repositories.document_repo import DocumentRepository
from app.services.chunking import chunk_text
from app.services.document_parsing import extract_text
from app.storage.s3_client import download_bytes
from app.vectorstore.qdrant_client import ensure_collection, upsert_chunks

logger = logging.getLogger("app.document_processing")


async def run_document_processing(
    provider_manager: ProviderManager, document_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Fire-and-forget: extracts text, chunks it, embeds it, and stores vectors in Qdrant.
    Never raises - failures are recorded on the document's status/error_message instead of
    breaking the upload response that already returned to the client."""
    settings = get_settings()
    async with async_session_factory() as db:
        repo = DocumentRepository(db)
        document = await repo.get_for_user(document_id, user_id)
        if not document:
            logger.error("Document %s not found for processing", document_id)
            return

        try:
            await repo.set_status(document, "processing")
            await db.commit()

            data = await download_bytes(document.storage_key)
            text = extract_text(document.content_type, data)
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("Chunking produced no chunks from extracted text")

            provider = provider_manager.get_provider(settings.embedding_provider)
            vectors = await provider.embed_texts(
                chunks, settings.embedding_model, output_dimensionality=settings.embedding_dimensions
            )

            await ensure_collection()
            await upsert_chunks(user_id, document_id, document.filename, chunks, vectors)

            await repo.set_status(document, "ready", chunk_count=len(chunks))
            await db.commit()
        except Exception as exc:
            logger.exception("Document processing failed for %s", document_id)
            await db.rollback()
            await repo.set_status(document, "failed", error_message=str(exc)[:500])
            await db.commit()
