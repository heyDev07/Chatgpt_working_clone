import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.scheduler import cancel_reminder_job, schedule_reminder_job
from app.models.reminder import Reminder
from app.repositories.reminder_repo import ReminderRepository


class ReminderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.reminders = ReminderRepository(db)

    async def create(
        self, user_id: uuid.UUID, message: str, remind_at: datetime, conversation_id: uuid.UUID | None = None
    ) -> Reminder:
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=timezone.utc)
        if remind_at <= datetime.now(timezone.utc):
            raise ValidationAppError("remind_at must be in the future")

        reminder = await self.reminders.create(user_id, message, remind_at, conversation_id)
        await self.db.commit()
        schedule_reminder_job(reminder.id, remind_at)
        return reminder

    async def list_for_user(self, user_id: uuid.UUID) -> list[Reminder]:
        return await self.reminders.list_for_user(user_id)

    async def list_due(self, user_id: uuid.UUID) -> list[Reminder]:
        return await self.reminders.list_due_undelivered(user_id)

    async def delete(self, reminder_id: uuid.UUID, user_id: uuid.UUID) -> None:
        reminder = await self.reminders.get_for_user(reminder_id, user_id)
        if not reminder:
            raise NotFoundError("Reminder not found")
        # Covers both real cancellation (deleting a reminder that hasn't fired yet) and
        # dismissal (the frontend deletes a delivered reminder once the user has seen its toast)
        # - either way, no job should be left behind trying to fire for a row that no longer
        # exists.
        cancel_reminder_job(reminder.id)
        await self.reminders.delete(reminder)
        await self.db.commit()
