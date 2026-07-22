import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository


class ConversationService:
    def __init__(self, db: AsyncSession, provider_manager: ProviderManager):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.provider_manager = provider_manager

    async def create(
        self, user_id: uuid.UUID, title: str | None, provider: str | None, model: str | None
    ) -> Conversation:
        provider_name = provider or self.provider_manager.get_default_provider_name()
        model_name = model or self.provider_manager.default_model_for(provider_name)

        conversation = await self.conversations.create(
            user_id=user_id,
            title=title or "New Conversation",
            provider=provider_name,
            model=model_name,
        )
        await self.db.commit()
        return conversation

    async def list_for_user(
        self, user_id: uuid.UUID, *, archived: bool = False, search: str | None = None
    ) -> list[Conversation]:
        return await self.conversations.list_for_user(user_id, archived=archived, search=search)

    async def get_detail(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get_with_messages(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        return conversation

    async def update(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_archived: bool | None = None,
    ) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        conversation = await self.conversations.update(
            conversation, title=title, is_pinned=is_pinned, is_archived=is_archived
        )
        await self.db.commit()
        return conversation

    async def delete(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> None:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        await self.conversations.delete(conversation)
        await self.db.commit()
