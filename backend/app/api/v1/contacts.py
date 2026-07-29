import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.contact import ContactOut, ContactUpsert
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ContactService:
    return ContactService(db)


@router.post("", response_model=ContactOut, status_code=201)
async def upsert_contact(
    payload: ContactUpsert,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(_get_service),
):
    return await service.upsert(current_user.id, payload.name, payload.relationship, payload.note)


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(_get_service),
):
    return await service.list_for_user(current_user.id)


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ContactService = Depends(_get_service),
):
    await service.delete(contact_id, current_user.id)
