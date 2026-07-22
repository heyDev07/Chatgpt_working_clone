import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory


class MemoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, user_id: uuid.UUID, category: str, memory_text: str, importance: float = 0.5
    ) -> Memory:
        memory = Memory(user_id=user_id, category=category, memory_text=memory_text, importance=importance)
        self.db.add(memory)
        await self.db.flush()
        return memory

    async def list_for_user(self, user_id: uuid.UUID) -> list[Memory]:
        result = await self.db.execute(
            select(Memory).where(Memory.user_id == user_id).order_by(Memory.importance.desc(), Memory.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, memory_id: uuid.UUID, user_id: uuid.UUID) -> Memory | None:
        result = await self.db.execute(
            select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        memory: Memory,
        *,
        memory_text: str | None = None,
        category: str | None = None,
        importance: float | None = None,
    ) -> Memory:
        if memory_text is not None:
            memory.memory_text = memory_text
        if category is not None:
            memory.category = category
        if importance is not None:
            memory.importance = importance
        await self.db.flush()
        await self.db.refresh(memory)
        return memory

    async def delete(self, memory: Memory) -> None:
        await self.db.delete(memory)
        await self.db.flush()

    async def top_for_user(self, user_id: uuid.UUID, limit: int = 10) -> list[Memory]:
        """Highest-importance, most-recent memories - used to inject into prompts."""
        result = await self.db.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
