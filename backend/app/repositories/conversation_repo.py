import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, title: str, provider: str, model: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, provider=provider, model=model)
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def list_for_user(self, user_id: uuid.UUID) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.is_archived.is_(False))
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_with_messages(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def delete(self, conversation: Conversation) -> None:
        await self.db.delete(conversation)
        await self.db.flush()

    async def touch(self, conversation: Conversation) -> None:
        """Bump updated_at so the sidebar's recency ordering reflects the latest message."""
        from sqlalchemy import func

        conversation.updated_at = func.now()
        await self.db.flush()
