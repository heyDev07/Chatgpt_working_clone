import uuid
from datetime import datetime

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        model: str | None = None,
        token_count: int | None = None,
        finish_reason: str | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            token_count=token_count,
            finish_reason=finish_reason,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def delete(self, message: Message) -> None:
        await self.db.delete(message)
        await self.db.flush()

    async def get_by_id(self, message_id: uuid.UUID, conversation_id: uuid.UUID) -> Message | None:
        result = await self.db.execute(
            select(Message).where(Message.id == message_id, Message.conversation_id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def delete_after(self, conversation_id: uuid.UUID, after: datetime) -> None:
        """Used when editing a message: discards everything that came after it, forking
        the conversation from the edit point."""
        await self.db.execute(
            sa_delete(Message).where(
                Message.conversation_id == conversation_id, Message.created_at > after
            )
        )
        await self.db.flush()

    async def set_feedback(self, message: Message, feedback: str | None) -> Message:
        message.feedback = feedback
        await self.db.flush()
        return message
