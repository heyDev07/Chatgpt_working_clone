import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.providers.provider_manager import ProviderManager
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.folder_repo import FolderRepository
from app.repositories.tag_repo import TagRepository


class ConversationService:
    def __init__(self, db: AsyncSession, provider_manager: ProviderManager):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.folders = FolderRepository(db)
        self.tags = TagRepository(db)
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
        self,
        user_id: uuid.UUID,
        *,
        archived: bool = False,
        search: str | None = None,
        folder_id: uuid.UUID | None = None,
        tag_id: uuid.UUID | None = None,
    ) -> list[Conversation]:
        return await self.conversations.list_for_user(
            user_id, archived=archived, search=search, folder_id=folder_id, tag_id=tag_id
        )

    async def add_tag(self, conversation_id: uuid.UUID, user_id: uuid.UUID, tag_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        tag = await self.tags.get_for_user(tag_id, user_id)
        if not tag:
            raise NotFoundError("Tag not found")
        conversation = await self.conversations.add_tag(conversation, tag)
        await self.db.commit()
        return conversation

    async def remove_tag(self, conversation_id: uuid.UUID, user_id: uuid.UUID, tag_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        tag = await self.tags.get_for_user(tag_id, user_id)
        if not tag:
            raise NotFoundError("Tag not found")
        conversation = await self.conversations.remove_tag(conversation, tag)
        await self.db.commit()
        return conversation

    async def set_folder(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, folder_id: uuid.UUID | None
    ) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        if folder_id is not None:
            folder = await self.folders.get_for_user(folder_id, user_id)
            if not folder:
                raise NotFoundError("Folder not found")
        conversation = await self.conversations.set_folder(conversation, folder_id)
        await self.db.commit()
        return conversation

    async def share(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        if not conversation.share_token:
            token = secrets.token_urlsafe(32)
            conversation = await self.conversations.set_share_token(conversation, token)
            await self.db.commit()
        return conversation

    async def unshare(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        conversation = await self.conversations.set_share_token(conversation, None)
        await self.db.commit()
        return conversation

    async def get_shared(self, share_token: str) -> Conversation:
        conversation = await self.conversations.get_by_share_token(share_token)
        if not conversation:
            raise NotFoundError("Shared conversation not found")
        return conversation

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
        provider: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
    ) -> Conversation:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        if provider is not None:
            self.provider_manager.get_provider(provider)  # raises if not a configured provider
        conversation = await self.conversations.update(
            conversation,
            title=title,
            is_pinned=is_pinned,
            is_archived=is_archived,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        await self.db.commit()
        return conversation

    async def delete(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> None:
        conversation = await self.conversations.get_for_user(conversation_id, user_id)
        if not conversation:
            raise NotFoundError("Conversation not found")
        await self.conversations.delete(conversation)
        await self.db.commit()
