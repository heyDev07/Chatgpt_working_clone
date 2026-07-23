from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_provider_manager
from app.providers.provider_manager import ProviderManager
from app.schemas.share import SharedConversationOut
from app.services.conversation_service import ConversationService

# No get_current_user dependency anywhere in this router - the token itself is the
# authorization, matching the "public read-only link" model (Google Docs-style share links).
router = APIRouter(prefix="/shared", tags=["shared"])


@router.get("/{share_token}", response_model=SharedConversationOut)
async def get_shared_conversation(
    share_token: str,
    db: AsyncSession = Depends(get_db),
    provider_manager: ProviderManager = Depends(get_provider_manager),
):
    service = ConversationService(db, provider_manager)
    return await service.get_shared(share_token)
