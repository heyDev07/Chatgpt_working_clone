import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder


class FolderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: uuid.UUID, name: str) -> Folder:
        folder = Folder(user_id=user_id, name=name)
        self.db.add(folder)
        await self.db.flush()
        return folder

    async def list_for_user(self, user_id: uuid.UUID) -> list[Folder]:
        result = await self.db.execute(
            select(Folder).where(Folder.user_id == user_id).order_by(Folder.name)
        )
        return list(result.scalars().all())

    async def get_for_user(self, folder_id: uuid.UUID, user_id: uuid.UUID) -> Folder | None:
        result = await self.db.execute(
            select(Folder).where(Folder.id == folder_id, Folder.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def rename(self, folder: Folder, name: str) -> Folder:
        folder.name = name
        await self.db.flush()
        await self.db.refresh(folder)
        return folder

    async def delete(self, folder: Folder) -> None:
        await self.db.delete(folder)
        await self.db.flush()
