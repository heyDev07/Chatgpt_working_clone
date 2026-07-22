import asyncio
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, StorageError, ValidationAppError
from app.models.document import Document
from app.providers.provider_manager import ProviderManager
from app.repositories.document_repo import DocumentRepository
from app.services.document_processing import run_document_processing
from app.storage.s3_client import delete_object, upload_bytes
from app.vectorstore.qdrant_client import delete_document_chunks

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


class DocumentService:
    def __init__(self, db: AsyncSession, provider_manager: ProviderManager):
        self.db = db
        self.provider_manager = provider_manager
        self.documents = DocumentRepository(db)

    async def upload(self, user_id: uuid.UUID, file: UploadFile) -> Document:
        content_type = file.content_type or ""
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationAppError(
                f"Unsupported file type '{content_type}'. Allowed: PDF, DOCX, TXT, CSV, XLSX."
            )

        data = await file.read()
        if not data:
            raise ValidationAppError("Uploaded file is empty.")
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise ValidationAppError("File exceeds the 20MB upload limit.")

        document = await self.documents.create(
            user_id=user_id,
            filename=file.filename or "untitled",
            content_type=content_type,
            size_bytes=len(data),
            storage_key="",  # set below once the document id is known
        )
        document.storage_key = f"{user_id}/{document.id}/{document.filename}"

        try:
            await upload_bytes(document.storage_key, data, content_type)
        except Exception as exc:
            await self.db.rollback()
            raise StorageError(f"Failed to store file: {exc}") from exc

        await self.db.commit()
        # storage_key was set after the initial insert, and updated_at has onupdate=func.now()
        # (server-computed) - without a refresh, accessing it after commit triggers a lazy-reload
        # outside the awaited async context (MissingGreenlet) once FastAPI serializes the response.
        await self.db.refresh(document)

        asyncio.create_task(run_document_processing(self.provider_manager, document.id, user_id))

        return document

    async def list_for_user(self, user_id: uuid.UUID) -> list[Document]:
        return await self.documents.list_for_user(user_id)

    async def get_for_user(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
        document = await self.documents.get_for_user(document_id, user_id)
        if not document:
            raise NotFoundError("Document not found")
        return document

    async def delete(self, document_id: uuid.UUID, user_id: uuid.UUID) -> None:
        document = await self.get_for_user(document_id, user_id)
        try:
            await delete_object(document.storage_key)
        except Exception:
            pass  # best-effort: still remove the DB record even if the object was already gone
        try:
            await delete_document_chunks(document.id)
        except Exception:
            pass  # best-effort: vector store may not have been populated yet (e.g. still processing)
        await self.documents.delete(document)
        await self.db.commit()
