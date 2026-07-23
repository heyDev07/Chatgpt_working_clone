import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tag import Tag


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, title: str, provider: str, model: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, provider=provider, model=model)
        self.db.add(conversation)
        await self.db.flush()
        # A many-to-many (secondary=) collection isn't known-empty for a persistent object the
        # way a plain FK-based one is - once flushed, accessing .tags would trigger a lazy
        # SELECT outside an awaited context (MissingGreenlet) during response serialization.
        # Explicitly loading it here (it's genuinely empty on a brand-new conversation) avoids
        # that without needing every caller to remember to selectinload a fresh object.
        await self.db.refresh(conversation, attribute_names=["tags"])
        return conversation

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        archived: bool = False,
        search: str | None = None,
        folder_id: uuid.UUID | None = None,
        tag_id: uuid.UUID | None = None,
    ) -> list[Conversation]:
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.is_archived.is_(archived))
            .options(selectinload(Conversation.tags))
        )
        if folder_id is not None:
            query = query.where(Conversation.folder_id == folder_id)
        if tag_id is not None:
            query = query.where(Conversation.tags.any(Tag.id == tag_id))
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
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .options(selectinload(Conversation.tags))
        )
        return result.scalar_one_or_none()

    async def get_with_messages(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages), selectinload(Conversation.tags))
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
        provider: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
    ) -> Conversation:
        if title is not None:
            conversation.title = title
        if is_pinned is not None:
            conversation.is_pinned = is_pinned
        if is_archived is not None:
            conversation.is_archived = is_archived
        if provider is not None:
            conversation.provider = provider
        if model is not None:
            conversation.model = model
        if system_prompt is not None:
            conversation.system_prompt = system_prompt
        if temperature is not None:
            conversation.temperature = temperature
        if max_tokens is not None:
            conversation.max_tokens = max_tokens
        if top_p is not None:
            conversation.top_p = top_p
        await self.db.flush()
        # updated_at has onupdate=func.now() (server-computed) - without an explicit refresh,
        # accessing it after this method returns triggers a lazy-reload outside the awaited
        # async context (MissingGreenlet), since serialization happens after the route returns.
        await self.db.refresh(conversation)
        return conversation

    async def set_folder(self, conversation: Conversation, folder_id: uuid.UUID | None) -> Conversation:
        # A dedicated method (rather than folding this into update()'s "None means don't touch"
        # convention) because None is a meaningful value here - it means "remove from folder".
        conversation.folder_id = folder_id
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def add_tag(self, conversation: Conversation, tag: Tag) -> Conversation:
        if tag not in conversation.tags:
            conversation.tags.append(tag)
            await self.db.flush()
            await self.db.refresh(conversation)
        return conversation

    async def remove_tag(self, conversation: Conversation, tag: Tag) -> Conversation:
        if tag in conversation.tags:
            conversation.tags.remove(tag)
            await self.db.flush()
            await self.db.refresh(conversation)
        return conversation

    async def touch(self, conversation: Conversation) -> None:
        """Bump updated_at so the sidebar's recency ordering reflects the latest message."""
        from sqlalchemy import func

        conversation.updated_at = func.now()
        await self.db.flush()
