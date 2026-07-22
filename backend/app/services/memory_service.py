import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.memory import Memory
from app.repositories.memory_repo import MemoryRepository


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.memories = MemoryRepository(db)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Memory]:
        return await self.memories.list_for_user(user_id)

    async def update(
        self,
        memory_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        memory_text: str | None = None,
        category: str | None = None,
        importance: float | None = None,
    ) -> Memory:
        memory = await self.memories.get_for_user(memory_id, user_id)
        if not memory:
            raise NotFoundError("Memory not found")
        memory = await self.memories.update(
            memory, memory_text=memory_text, category=category, importance=importance
        )
        await self.db.commit()
        return memory

    async def delete(self, memory_id: uuid.UUID, user_id: uuid.UUID) -> None:
        memory = await self.memories.get_for_user(memory_id, user_id)
        if not memory:
            raise NotFoundError("Memory not found")
        await self.memories.delete(memory)
        await self.db.commit()
