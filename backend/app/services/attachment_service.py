import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, StorageError, ValidationAppError
from app.models.message_attachment import MessageAttachment
from app.repositories.message_attachment_repo import MessageAttachmentRepository
from app.storage.s3_client import download_bytes, safe_storage_filename, upload_bytes

ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# Same five types document_service.py's Knowledge Base upload accepts - a document attached here
# goes through the identical parse step (document_parsing.extract_text), just indexed
# conversation-scoped in chat_service.py instead of into the user's global Knowledge Base. Capped
# smaller than the Knowledge Base's 20MB since this one is parsed/chunked/embedded synchronously
# inline in the message-send request, not as a fire-and-forget background job - it needs to stay
# light enough not to make sending a message noticeably slow.
ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_DOCUMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


class AttachmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.attachments = MessageAttachmentRepository(db)

    async def upload(self, user_id: uuid.UUID, file: UploadFile) -> MessageAttachment:
        content_type = file.content_type or ""
        is_document = content_type in ALLOWED_DOCUMENT_CONTENT_TYPES
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES and not is_document:
            raise ValidationAppError(
                f"Unsupported file type '{content_type}'. Allowed: PNG, JPEG, WEBP, GIF, PDF, DOCX, TXT, CSV, XLSX."
            )

        data = await file.read()
        if not data:
            raise ValidationAppError("Uploaded file is empty.")
        max_size = MAX_DOCUMENT_SIZE_BYTES if is_document else MAX_IMAGE_SIZE_BYTES
        if len(data) > max_size:
            limit_mb = max_size // (1024 * 1024)
            raise ValidationAppError(f"File exceeds the {limit_mb}MB upload limit.")

        attachment = await self.attachments.create(
            user_id=user_id,
            filename=file.filename or "image",
            content_type=content_type,
            size_bytes=len(data),
            storage_key="",  # set below once the attachment id is known
        )
        attachment.storage_key = f"attachments/{user_id}/{attachment.id}/{safe_storage_filename(attachment.filename)}"

        try:
            await upload_bytes(attachment.storage_key, data, content_type)
        except Exception as exc:
            await self.db.rollback()
            raise StorageError(f"Failed to store file: {exc}") from exc

        await self.db.commit()
        return attachment

    async def get_content(self, attachment_id: uuid.UUID, user_id: uuid.UUID) -> tuple[bytes, str]:
        attachment = await self.attachments.get_for_user(attachment_id, user_id)
        if not attachment:
            raise NotFoundError("Attachment not found")
        data = await download_bytes(attachment.storage_key)
        return data, attachment.content_type
