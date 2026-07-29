import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.contact import Contact
from app.repositories.contact_repo import ContactRepository


class ContactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.contacts = ContactRepository(db)

    async def upsert(
        self,
        user_id: uuid.UUID,
        name: str,
        relationship: str | None = None,
        note: str | None = None,
        last_contact_at: datetime | None = None,
    ) -> Contact:
        """Merges into an existing same-name contact rather than creating a duplicate - see the
        Contact model's docstring for why. relationship/last_contact_at overwrite (the caller is
        stating the current fact), notes append as a new line (a log, not a summary) so an
        earlier note about this person isn't silently lost when a later one is added."""
        existing = await self.contacts.get_by_name(user_id, name)
        if existing is None:
            contact = await self.contacts.create(user_id, name, relationship, note, last_contact_at)
            await self.db.commit()
            return contact

        if relationship is not None:
            existing.relationship = relationship
        if note is not None:
            existing.notes = f"{existing.notes}\n{note}" if existing.notes else note
        if last_contact_at is not None:
            existing.last_contact_at = last_contact_at
        await self.db.commit()
        return existing

    async def list_for_user(self, user_id: uuid.UUID) -> list[Contact]:
        return await self.contacts.list_for_user(user_id)

    async def delete(self, contact_id: uuid.UUID, user_id: uuid.UUID) -> None:
        contact = await self.contacts.get_for_user(contact_id, user_id)
        if not contact:
            raise NotFoundError("Contact not found")
        await self.contacts.delete(contact)
        await self.db.commit()
