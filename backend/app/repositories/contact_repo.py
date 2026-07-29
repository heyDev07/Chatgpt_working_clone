import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact


class ContactRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_name(self, user_id: uuid.UUID, name: str) -> Contact | None:
        result = await self.db.execute(
            select(Contact).where(Contact.user_id == user_id, Contact.name == name)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        relationship: str | None,
        notes: str | None,
        last_contact_at: datetime | None,
    ) -> Contact:
        contact = Contact(
            user_id=user_id,
            name=name,
            relationship=relationship,
            notes=notes,
            last_contact_at=last_contact_at,
        )
        self.db.add(contact)
        await self.db.flush()
        return contact

    async def list_for_user(self, user_id: uuid.UUID) -> list[Contact]:
        result = await self.db.execute(
            select(Contact).where(Contact.user_id == user_id).order_by(Contact.name.asc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, contact_id: uuid.UUID, user_id: uuid.UUID) -> Contact | None:
        result = await self.db.execute(
            select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, contact: Contact) -> None:
        await self.db.delete(contact)
        await self.db.flush()
