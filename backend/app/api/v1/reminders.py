import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.reminder import ReminderCreate, ReminderOut
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ReminderService:
    return ReminderService(db)


@router.post("", response_model=ReminderOut, status_code=201)
async def create_reminder(
    payload: ReminderCreate,
    current_user: User = Depends(get_current_user),
    service: ReminderService = Depends(_get_service),
):
    return await service.create(current_user.id, payload.message, payload.remind_at, payload.conversation_id)


@router.get("", response_model=list[ReminderOut])
async def list_reminders(
    due: bool = False,
    current_user: User = Depends(get_current_user),
    service: ReminderService = Depends(_get_service),
):
    # ?due=true is what the frontend polls to know when to show a toast - only reminders whose
    # scheduled job has actually fired (is_delivered), not just anything with a past remind_at,
    # since the scheduler is the one source of truth for "this has actually happened" rather
    # than the frontend re-deriving it from the current time itself.
    if due:
        return await service.list_due(current_user.id)
    return await service.list_for_user(current_user.id)


@router.delete("/{reminder_id}", status_code=204)
async def delete_reminder(
    reminder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ReminderService = Depends(_get_service),
):
    await service.delete(reminder_id, current_user.id)
