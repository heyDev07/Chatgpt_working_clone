import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag


class TagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, name: str) -> Tag:
        tag = Tag(user_id=user_id, name=name)
        self.db.add(tag)
        await self.db.flush()
        return tag

    async def list_for_user(self, user_id: uuid.UUID) -> list[Tag]:
        result = await self.db.execute(select(Tag).where(Tag.user_id == user_id).order_by(Tag.name))
        return list(result.scalars().all())

    async def get_for_user(self, tag_id: uuid.UUID, user_id: uuid.UUID) -> Tag | None:
        result = await self.db.execute(select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, user_id: uuid.UUID, name: str) -> Tag | None:
        result = await self.db.execute(select(Tag).where(Tag.user_id == user_id, Tag.name == name))
        return result.scalar_one_or_none()

    async def delete(self, tag: Tag) -> None:
        await self.db.delete(tag)
        await self.db.flush()
