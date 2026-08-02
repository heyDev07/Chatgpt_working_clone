import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_provider_manager, get_redis
from app.middleware.rate_limit import upload_rate_limiter
from app.models.user import User
from app.providers.provider_manager import ProviderManager
from app.schemas.document import DocumentOut
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_service(
    db: AsyncSession = Depends(get_db),
    provider_manager: ProviderManager = Depends(get_provider_manager),
) -> DocumentService:
    return DocumentService(db, provider_manager)


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(_get_service),
    redis: Redis = Depends(get_redis),
):
    # Parsing + embedding a document costs real compute (and, for the embedding call, real API
    # spend) - this endpoint had no rate limit at all before, unlike message sends.
    await upload_rate_limiter.check(redis, identifier=str(current_user.id))
    return await service.upload(current_user.id, file)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(_get_service),
):
    return await service.list_for_user(current_user.id)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(_get_service),
):
    return await service.get_for_user(document_id, current_user.id)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(_get_service),
):
    await service.delete(document_id, current_user.id)


@router.post("/{document_id}/set-resume", response_model=DocumentOut)
async def set_resume(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(_get_service),
):
    return await service.set_resume(document_id, current_user.id)
