import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.memory import MemoryOut, MemoryUpdate
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


def _get_service(db: AsyncSession = Depends(get_db)) -> MemoryService:
    return MemoryService(db)


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    current_user: User = Depends(get_current_user),
    service: MemoryService = Depends(_get_service),
):
    return await service.list_for_user(current_user.id)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    current_user: User = Depends(get_current_user),
    service: MemoryService = Depends(_get_service),
):
    return await service.update(
        memory_id,
        current_user.id,
        memory_text=payload.memory_text,
        category=payload.category,
        importance=payload.importance,
    )


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: MemoryService = Depends(_get_service),
):
    await service.delete(memory_id, current_user.id)
