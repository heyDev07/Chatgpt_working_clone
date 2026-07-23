import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.tag import TagCreate, TagOut
from app.services.tag_service import TagService

router = APIRouter(prefix="/tags", tags=["tags"])


def _get_service(db: AsyncSession = Depends(get_db)) -> TagService:
    return TagService(db)


@router.post("", response_model=TagOut, status_code=201)
async def create_tag(
    payload: TagCreate,
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(_get_service),
):
    return await service.create(current_user.id, payload.name)


@router.get("", response_model=list[TagOut])
async def list_tags(
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(_get_service),
):
    return await service.list_for_user(current_user.id)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: TagService = Depends(_get_service),
):
    await service.delete(tag_id, current_user.id)
