import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message_attachment import MessageAttachment


class MessageAttachmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, user_id: uuid.UUID, filename: str, content_type: str, size_bytes: int, storage_key: str
    ) -> MessageAttachment:
        attachment = MessageAttachment(
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
        )
        self.db.add(attachment)
        await self.db.flush()
        return attachment

    async def create_for_message(
        self,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
    ) -> MessageAttachment:
        """For attachments that never went through the upload endpoint - an assistant-generated
        image (generate_image tool) already has bytes in S3 and a message to attach to by the
        time this is called, unlike a user upload's create()-then-attach_to_message() two-step."""
        attachment = MessageAttachment(
            user_id=user_id,
            message_id=message_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
        )
        self.db.add(attachment)
        await self.db.flush()
        return attachment

    async def get_for_user(self, attachment_id: uuid.UUID, user_id: uuid.UUID) -> MessageAttachment | None:
        result = await self.db.execute(
            select(MessageAttachment).where(
                MessageAttachment.id == attachment_id, MessageAttachment.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def attach_to_message(
        self, attachment_ids: list[uuid.UUID], message_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[MessageAttachment]:
        """Links previously-uploaded, still-unattached attachments to a just-created message.
        Scoped to (id, user_id, message_id IS NULL) so a user can't attach someone else's
        upload, or re-attach one that's already linked to a different message."""
        if not attachment_ids:
            return []
        result = await self.db.execute(
            select(MessageAttachment).where(
                MessageAttachment.id.in_(attachment_ids),
                MessageAttachment.user_id == user_id,
                MessageAttachment.message_id.is_(None),
            )
        )
        attachments = list(result.scalars().all())
        for attachment in attachments:
            attachment.message_id = message_id
        await self.db.flush()
        return attachments

    async def list_for_messages(self, message_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[MessageAttachment]]:
        if not message_ids:
            return {}
        result = await self.db.execute(
            select(MessageAttachment).where(MessageAttachment.message_id.in_(message_ids))
        )
        by_message: dict[uuid.UUID, list[MessageAttachment]] = {}
        for attachment in result.scalars().all():
            by_message.setdefault(attachment.message_id, []).append(attachment)
        return by_message
