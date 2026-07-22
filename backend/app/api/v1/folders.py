import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.folder import FolderCreate, FolderOut, FolderUpdate
from app.services.folder_service import FolderService

router = APIRouter(prefix="/folders", tags=["folders"])


def _get_service(db: AsyncSession = Depends(get_db)) -> FolderService:
    return FolderService(db)


@router.post("", response_model=FolderOut, status_code=201)
async def create_folder(
    payload: FolderCreate,
    current_user: User = Depends(get_current_user),
    service: FolderService = Depends(_get_service),
):
    return await service.create(current_user.id, payload.name)


@router.get("", response_model=list[FolderOut])
async def list_folders(
    current_user: User = Depends(get_current_user),
    service: FolderService = Depends(_get_service),
):
    return await service.list_for_user(current_user.id)


@router.patch("/{folder_id}", response_model=FolderOut)
async def rename_folder(
    folder_id: uuid.UUID,
    payload: FolderUpdate,
    current_user: User = Depends(get_current_user),
    service: FolderService = Depends(_get_service),
):
    return await service.rename(folder_id, current_user.id, payload.name)


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: FolderService = Depends(_get_service),
):
    await service.delete(folder_id, current_user.id)
