import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.tag import Tag
from app.repositories.tag_repo import TagRepository


class TagService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tags = TagRepository(db)

    async def create(self, user_id: uuid.UUID, name: str) -> Tag:
        existing = await self.tags.get_by_name(user_id, name)
        if existing:
            raise ValidationAppError("A tag with this name already exists")
        tag = await self.tags.create(user_id, name)
        await self.db.commit()
        return tag

    async def list_for_user(self, user_id: uuid.UUID) -> list[Tag]:
        return await self.tags.list_for_user(user_id)

    async def delete(self, tag_id: uuid.UUID, user_id: uuid.UUID) -> None:
        tag = await self.tags.get_for_user(tag_id, user_id)
        if not tag:
            raise NotFoundError("Tag not found")
        await self.tags.delete(tag)
        await self.db.commit()
