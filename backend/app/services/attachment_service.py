import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, StorageError, ValidationAppError
from app.models.message_attachment import MessageAttachment
from app.repositories.message_attachment_repo import MessageAttachmentRepository
from app.storage.s3_client import download_bytes, safe_storage_filename, upload_bytes

ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class AttachmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.attachments = MessageAttachmentRepository(db)

    async def upload(self, user_id: uuid.UUID, file: UploadFile) -> MessageAttachment:
        content_type = file.content_type or ""
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValidationAppError(
                f"Unsupported file type '{content_type}'. Allowed: PNG, JPEG, WEBP, GIF."
            )

        data = await file.read()
        if not data:
            raise ValidationAppError("Uploaded file is empty.")
        if len(data) > MAX_IMAGE_SIZE_BYTES:
            raise ValidationAppError("Image exceeds the 10MB upload limit.")

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
