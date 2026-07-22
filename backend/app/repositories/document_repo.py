import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, user_id: uuid.UUID, filename: str, content_type: str, size_bytes: int, storage_key: str
    ) -> Document:
        document = Document(
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            status="pending",
        )
        self.db.add(document)
        await self.db.flush()
        return document

    async def list_for_user(self, user_id: uuid.UUID) -> list[Document]:
        result = await self.db.execute(
            select(Document).where(Document.user_id == user_id).order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def set_status(
        self, document: Document, status: str, *, chunk_count: int | None = None, error_message: str | None = None
    ) -> Document:
        document.status = status
        if chunk_count is not None:
            document.chunk_count = chunk_count
        if error_message is not None:
            document.error_message = error_message
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def delete(self, document: Document) -> None:
        await self.db.delete(document)
        await self.db.flush()
