import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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

    async def has_ready_documents(self, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == user_id, Document.status == "ready")
        )
        return (result.scalar_one() or 0) > 0

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

    async def get_resume_for_user(self, user_id: uuid.UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(Document.user_id == user_id, Document.is_resume.is_(True))
        )
        return result.scalar_one_or_none()

    async def set_resume(self, user_id: uuid.UUID, document_id: uuid.UUID) -> Document:
        """Marks one document as the user's active resume, atomically un-marking any previous
        one - at most one resume per user is a real invariant (get_resume_text has nowhere to
        send an ambiguous "which one" question), enforced here rather than a DB constraint since
        this is the only call site that ever changes is_resume."""
        document = await self.get_for_user(document_id, user_id)
        if document is None:
            raise NotFoundError("Document not found")
        await self.db.execute(
            update(Document).where(Document.user_id == user_id, Document.id != document_id).values(is_resume=False)
        )
        document.is_resume = True
        await self.db.flush()
        await self.db.refresh(document)
        return document
