import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.folder import Folder
from app.repositories.folder_repo import FolderRepository


class FolderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.folders = FolderRepository(db)

    async def create(self, user_id: uuid.UUID, name: str) -> Folder:
        folder = await self.folders.create(user_id, name)
        await self.db.commit()
        return folder

    async def list_for_user(self, user_id: uuid.UUID) -> list[Folder]:
        return await self.folders.list_for_user(user_id)

    async def rename(self, folder_id: uuid.UUID, user_id: uuid.UUID, name: str) -> Folder:
        folder = await self.folders.get_for_user(folder_id, user_id)
        if not folder:
            raise NotFoundError("Folder not found")
        folder = await self.folders.rename(folder, name)
        await self.db.commit()
        return folder

    async def delete(self, folder_id: uuid.UUID, user_id: uuid.UUID) -> None:
        folder = await self.folders.get_for_user(folder_id, user_id)
        if not folder:
            raise NotFoundError("Folder not found")
        await self.folders.delete(folder)
        await self.db.commit()
