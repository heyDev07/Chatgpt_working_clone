import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder


class ReminderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        message: str,
        remind_at: datetime,
        conversation_id: uuid.UUID | None = None,
    ) -> Reminder:
        reminder = Reminder(user_id=user_id, message=message, remind_at=remind_at, conversation_id=conversation_id)
        self.db.add(reminder)
        await self.db.flush()
        return reminder

    async def list_for_user(self, user_id: uuid.UUID) -> list[Reminder]:
        result = await self.db.execute(
            select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.remind_at.asc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, reminder_id: uuid.UUID, user_id: uuid.UUID) -> Reminder | None:
        result = await self.db.execute(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, reminder: Reminder) -> None:
        await self.db.delete(reminder)
        await self.db.flush()

    async def mark_delivered(self, reminder_id: uuid.UUID) -> None:
        """Looked up by id alone (not scoped to a user) - called from the scheduler's fired-job
        callback, which only ever has the id it scheduled the job with, not a request-scoped
        user context."""
        result = await self.db.execute(select(Reminder).where(Reminder.id == reminder_id))
        reminder = result.scalar_one_or_none()
        if reminder is not None:
            reminder.is_delivered = True
            await self.db.flush()

    async def list_due_undelivered(self, user_id: uuid.UUID) -> list[Reminder]:
        """Delivered-but-not-yet-seen reminders - the frontend polls this to show a toast the
        moment a reminder's time has passed, then the frontend itself is responsible for marking
        it seen (deleting or otherwise) rather than this query only ever returning it once."""
        result = await self.db.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id, Reminder.is_delivered.is_(True))
            .order_by(Reminder.remind_at.asc())
        )
        return list(result.scalars().all())
