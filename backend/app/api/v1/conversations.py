import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_provider_manager
from app.models.user import User
from app.providers.provider_manager import ProviderManager
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationUpdate,
)
from app.schemas.folder import ConversationFolderUpdate
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_service(
    db: AsyncSession = Depends(get_db),
    provider_manager: ProviderManager = Depends(get_provider_manager),
) -> ConversationService:
    return ConversationService(db, provider_manager)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_get_service),
):
    return await service.create(current_user.id, payload.title, payload.provider, payload.model)


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    archived: bool = False,
    search: str | None = None,
    folder_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_get_service),
):
    return await service.list_for_user(current_user.id, archived=archived, search=search, folder_id=folder_id)


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_get_service),
):
    return await service.get_detail(conversation_id, current_user.id)


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_get_service),
):
    return await service.update(
        conversation_id,
        current_user.id,
        title=payload.title,
        is_pinned=payload.is_pinned,
        is_archived=payload.is_archived,
        provider=payload.provider,
        model=payload.model,
        system_prompt=payload.system_prompt,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        top_p=payload.top_p,
    )


@router.patch("/{conversation_id}/folder", response_model=ConversationOut)
async def set_conversation_folder(
    conversation_id: uuid.UUID,
    payload: ConversationFolderUpdate,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_get_service),
):
    return await service.set_folder(conversation_id, current_user.id, payload.folder_id)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(_get_service),
):
    await service.delete(conversation_id, current_user.id)
