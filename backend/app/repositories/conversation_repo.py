import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, title: str, provider: str, model: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, provider=provider, model=model)
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def list_for_user(
        self, user_id: uuid.UUID, *, archived: bool = False, search: str | None = None
    ) -> list[Conversation]:
        query = select(Conversation).where(
            Conversation.user_id == user_id, Conversation.is_archived.is_(archived)
        )
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    Conversation.title.ilike(pattern),
                    Conversation.id.in_(
                        select(Message.conversation_id).where(Message.content.ilike(pattern))
                    ),
                )
            )
        query = query.order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
        result = await self.db.execute(query)
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

    async def update(
        self,
        conversation: Conversation,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_archived: bool | None = None,
    ) -> Conversation:
        if title is not None:
            conversation.title = title
        if is_pinned is not None:
            conversation.is_pinned = is_pinned
        if is_archived is not None:
            conversation.is_archived = is_archived
        await self.db.flush()
        # updated_at has onupdate=func.now() (server-computed) - without an explicit refresh,
        # accessing it after this method returns triggers a lazy-reload outside the awaited
        # async context (MissingGreenlet), since serialization happens after the route returns.
        await self.db.refresh(conversation)
        return conversation

    async def touch(self, conversation: Conversation) -> None:
        """Bump updated_at so the sidebar's recency ordering reflects the latest message."""
        from sqlalchemy import func

        conversation.updated_at = func.now()
        await self.db.flush()
